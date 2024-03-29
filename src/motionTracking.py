"""
Motion tracking of contours via camera
"""

# Imports
import os
import math
import numpy as np
import cv2
import pygame

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (210, 210, 210)
RED = (255, 0, 0)
GREEN = (20, 255, 140)
BLUE = (0, 0, 255)
GOLD = (255, 215, 0)
SILVER = (192, 192, 192)

# Camera Settings
cameraAutodetect = False
resolution = "FullHD"  # 'FullHD', 'HD', 'SD'
cameraID = 0  # Camera device index (only when camera autodetect is off)
cameraFps = 30
contourDetectionPoints = 650  # Indicates how many contour points needed to detect motion
numRandomContours = 500  # 0 = Original contour points; needs to be smaller/equal than contour detection points
gaussianBlurKSize = (31, 31)  # Odd number required
thresholdValue = 5
thresholdMaxValue = 255
erodingIter = 4
dilatingIter = 8
clusteringIter = 10
clusteringEpsilon = 1.0
showContours = True
showCentroid = True
centroidSize = 25  # Integer required
displayFrames = False

# Setting resolutions
if resolution == "FullHD":
    width, height = 1920, 1080
elif resolution == "HD":
    width, height = 1280, 720
elif resolution == "SD":
    width, height = 1024, 576


# Convert from fourcc numerical code to fourcc string character code
def decode_fourcc(cc):
    """
    :param cc: fourcc numerical code
    :return: fourcc string character code
    """
    return "".join([chr((int(cc) >> 8 * i) & 0xFF) for i in range(4)])


# Init camera
def cameraStart():
    """
    :return: video input
    """
    if cameraAutodetect:
        camera = cv2.VideoCapture(0, cv2.CAP_ANY)
    else:
        camera = cv2.VideoCapture(cameraID, cv2.CAP_DSHOW)
    camera.set(3, width)
    camera.set(4, height)
    camera.set(5, cameraFps)
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    print("Camera backend:", camera.getBackendName())
    print("Codec:", decode_fourcc(camera.get(6)))
    return camera


# Manipulate images
def imageProcessing(camera, master):
    """
    :param camera: video input
    :param master: frame placeholder
    :return: manipulated images
    """
    (grabbed, frame0) = camera.read()  # Grab a frame
    if not grabbed:  # End of feed
        return None, None, None, None, 'break'

    frame1 = cv2.cvtColor(frame0, cv2.COLOR_BGR2GRAY)  # Gray frame
    frame2 = cv2.GaussianBlur(frame1, gaussianBlurKSize, 0)  # Blur frame

    # Initialize master
    if master is None:
        master = frame2
        return master, None, None, None, 'continue'

    frame3 = cv2.absdiff(master, frame2)  # Delta frame
    frame4 = cv2.threshold(frame3, thresholdValue, thresholdMaxValue, cv2.THRESH_BINARY)[1]  # Threshold frame

    # Dilate the thresholded image to fill in holes
    kernel = np.ones((2, 2), np.uint8)
    frame5 = cv2.erode(frame4, kernel, iterations=erodingIter)
    frame5 = cv2.dilate(frame5, kernel, iterations=dilatingIter)  # Dialated frame

    # Find contours on thresholded image
    contours, hierarchy = cv2.findContours(frame5.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    master = frame2  # Update master
    frames = [frame0, frame1, frame2, frame3, frame4, frame5]  # Collect frames
    return master, contours, hierarchy, frames, 'None'


# Init cluster parameters
def clusterParams(multiTouch):
    """
    :param multiTouch: boolean about enabling multi touch
    :return: parameters for clustering
    """
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                clusteringIter, clusteringEpsilon)  # Define criteria for kmeans
    clusterA, clusterB, center = [[0, 0]], [[0, 0]], [[0, 0], [0, 0]]
    clusterNumber = 1
    if multiTouch:
        clusterNumber = 2
    return criteria, clusterNumber, clusterA, clusterB, center, []


# Clustering contour points
def contourClustering(contours, criteria, clusterNumber, multiTouch):
    """
    :param contours: array of contour coordinates
    :param criteria: parameters for clustering
    :param clusterNumber: number of clusters to be generated
    :param multiTouch: boolean about enabling multi touch
    :return: clustered contours and corresponding centroid
    """
    contourCoordinates = []
    for i in contours:
        for j in range(len(i)):
            contourCoordinates.append(i[j][0])  # Save contour point coordinates

    contourCoordinates = np.float32(contourCoordinates)
    ret, label, center = cv2.kmeans(contourCoordinates, clusterNumber, None,
                                    criteria, 10, cv2.KMEANS_RANDOM_CENTERS)  # Apply kmeans clustering
    clusterA = contourCoordinates[label.ravel() == 0]  # Cluster input A
    clusterB = []
    if multiTouch:
        clusterB = contourCoordinates[label.ravel() == 1]  # Cluster input B
    return clusterA, clusterB, center, ret


# Tracking centroid
def centroidTracking(clusterA, clusterB, center, previousCenter):
    """
    :param clusterA: array of clustered contour coordinates
    :param clusterB: array of clustered contour coordinates
    :param center: array of center coordinates
    :param previousCenter: array of previous center coordinates
    :return: relabeled cluster and center
    """
    comparisonCenterCoordinates = []
    comparisonCenterCoordinates.extend([center[0], center[1], previousCenter[1]])

    # Find smallest distance between previous center A and previous/current centers' coordinates
    minDistance = float('inf')  # Set initial minimum distance
    distanceListCenter, minCoordinatesCenter = [], [0, 0]
    for i in comparisonCenterCoordinates:
        distanceListCenter.append(math.sqrt((previousCenter[0][0] - i[0]) ** 2 +
                                            (previousCenter[0][1] - i[1]) ** 2))
        if distanceListCenter[-1] < minDistance:
            minDistance = distanceListCenter[-1]
            minCoordinatesCenter = i
    # If smallest distance is center B: swap both cluster and center
    if (minCoordinatesCenter == comparisonCenterCoordinates[1]).all():
        tmpClusterA = clusterA
        clusterA = clusterB
        clusterB = tmpClusterA
        center = [center[1], center[0]]
    return clusterA, clusterB, center


# Display contours
def displayContours(data, screen, sContours, multiTouch):
    """
    :param data: array of contour coordinates
    :param screen: pygame screen
    :param sContours: boolean about rendering contours
    :param multiTouch: boolean about enabling multi touch
    """
    if sContours:
        for i in range(len(data[2])):
            pygame.draw.circle(screen, RED, (int(round(data[2][i][0])),
                                             int(round(data[2][i][1]))), 1)  # Render cluster A
        if multiTouch:
            for i in range(len(data[3])):
                pygame.draw.circle(screen, BLUE, (int(round(data[3][i][0])),
                                                  int(round(data[3][i][1]))), 1)  # Render cluster B


# Display input
def displayInput(minCoordinatesClusterA, minCoordinatesClusterB, inputSize, screen, multiTouch):
    """
    :param minCoordinatesClusterA:
    :param minCoordinatesClusterB:
    :param inputSize:
    :param screen:
    :param multiTouch:
    """
    pygame.draw.circle(screen, RED, (int(round(minCoordinatesClusterA[0])),
                                     int(round(minCoordinatesClusterA[1]))), inputSize)  # Render centroid A
    if multiTouch:
        pygame.draw.circle(screen, BLUE, (int(round(minCoordinatesClusterB[0])),
                                          int(round(minCoordinatesClusterB[1]))), inputSize)  # Render centroid B


# Display centroid
def displayCentroid(data, screen, sContours, sCentroid, cSize, multiTouch):
    """
    :param data: array of centroid coordinates
    :param screen: pygame screen
    :param sContours: boolean about rendering contours
    :param sCentroid: boolean about rendering centroid
    :param cSize: integer defining centroid size
    :param multiTouch: boolean about enabling multi touch
    """
    if sCentroid:
        cidx = 4
        if sContours is False:
            cidx = 2
        pygame.draw.circle(screen, GOLD, (int(round(data[cidx][0][0])),
                                          int(round(data[cidx][0][1]))), cSize)  # Render centroid cluster A
        if multiTouch:
            pygame.draw.circle(screen, GOLD, (int(round(data[cidx][1][0])),
                                              int(round(data[cidx][1][1]))), cSize)  # Render centroid cluster B


# Display cameras
def displayAllFrames(data, sContours, sCentroid, dFrames):
    """
    :param data: array of all 5 different frames
    :param sContours: boolean about rendering contours
    :param sCentroid: boolean about rendering centroid
    :param dFrames: boolean about rendering frames
    """
    if dFrames:
        fidx = 5
        if sContours is False:
            fidx = 3
        if sCentroid is False:
            fidx = 4
        if sContours is False and sCentroid is False:
            fidx = 2
        # Show frames
        cv2.imshow("Frame0: Raw", data[fidx][0])
        cv2.imshow("Frame1: Gray", data[fidx][1])
        cv2.imshow("Frame2: Blur", data[fidx][2])
        cv2.imshow("Frame3: Delta", data[fidx][3])
        cv2.imshow("Frame4: Threshold", data[fidx][4])
        cv2.imshow("Frame5: Dialated", data[fidx][5])
