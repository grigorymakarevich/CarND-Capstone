#!/usr/bin/env python
import rospy
from std_msgs.msg import Int32
from geometry_msgs.msg import PoseStamped, Pose
from styx_msgs.msg import TrafficLightArray, TrafficLight
from styx_msgs.msg import Lane
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from light_classification.tl_classifier import TLClassifier
import tf
import cv2
import yaml

import math

STATE_COUNT_THRESHOLD = 3
MAX_LIGHTS_DISTANCE = 300
MIN_LIGHTS_DISTANCE = 20

class GroundTruthBuilder(object):
    def __init__(self):
        self.red_count = 0;
        self.yellow_count = 0;
        self.green_count = 0;
        self.images_dir = "/home/student/saved_images"
        self.red_dir = self.images_dir + "/red"
        self.yellow_dir = self.images_dir + "/yellow"
        self.green_dir = self.images_dir + "/green"

    def save_image(self, light, image):
        img_file = None
        if light == TrafficLight.RED:
            self.red_count = self.red_count + 1
            img_file = '%s/%d.png' % (self.red_dir, self.red_count)
        elif light == TrafficLight.YELLOW:
            self.yellow_count = self.yellow_count + 1
            img_file = '%s/%d.png' % (self.yellow_dir, self.yellow_count)
        elif light == TrafficLight.GREEN:
            self.green_count = self.green_count + 1
            img_file = '%s/%d.png' % (self.green_dir, self.green_count)

        if img_file is not None:
            rospy.loginfo("img_file %s", img_file)
            cv2.imwrite(img_file, image)
            rospy.loginfo("Total: %d; Red: %d; Yellow: %d; Green: %d",
                          (self.red_count + self.yellow_count + self.green_count),
                          self.red_count, self.yellow_count, self.green_count)

class TLDetector(object):
    def __init__(self):
        rospy.init_node('tl_detector')

        self.pose = None
        self.waypoints = None
        self.camera_image = None
        self.lights = []

        sub1 = rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb)
        sub2 = rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb)

        '''
        /vehicle/traffic_lights provides you with the location of the traffic light in 3D map space and
        helps you acquire an accurate ground truth data source for the traffic light
        classifier by sending the current color state of all traffic lights in the
        simulator. When testing on the vehicle, the color state will not be available. You'll need to
        rely on the position of the light and the camera image to predict it.
        '''
        sub3 = rospy.Subscriber('/vehicle/traffic_lights', TrafficLightArray, self.traffic_cb)
        sub6 = rospy.Subscriber('/image_color', Image, self.image_cb)

        config_string = rospy.get_param("/traffic_light_config")
        self.config = yaml.load(config_string)

        self.upcoming_red_light_pub = rospy.Publisher('/traffic_waypoint', Int32, queue_size=1)

        self.bridge = CvBridge()
        self.light_classifier = TLClassifier()
        self.listener = tf.TransformListener()

        self.state = TrafficLight.UNKNOWN
        self.last_state = TrafficLight.UNKNOWN
        self.last_wp = -1
        self.state_count = 0

        self.gt_builer = GroundTruthBuilder()

        rospy.spin()

    def pose_cb(self, msg):
        self.pose = msg

    def waypoints_cb(self, waypoints):
        self.waypoints = waypoints

    def traffic_cb(self, msg):
        self.lights = msg.lights

    def image_cb(self, msg):
        """Identifies red lights in the incoming camera image and publishes the index
            of the waypoint closest to the red light's stop line to /traffic_waypoint

        Args:
            msg (Image): image from car-mounted camera

        """
        self.has_image = True
        self.camera_image = msg

        light = self.get_closest_light(self.pose, self.lights)
        if light is not None:
            # rospy.loginfo('Got a light %s' % light.state)
            cv_image = self.bridge.imgmsg_to_cv2(self.camera_image, "bgr8")
            self.gt_builer.save_image(light.state, cv_image)
        
        light_wp, state = self.process_traffic_lights()

        '''
        Publish upcoming red lights at camera frequency.
        Each predicted state has to occur `STATE_COUNT_THRESHOLD` number
        of times till we start using it. Otherwise the previous stable state is
        used.
        '''
        if self.state != state:
            self.state_count = 0
            self.state = state
        elif self.state_count >= STATE_COUNT_THRESHOLD:
            self.last_state = self.state
            light_wp = light_wp if state == TrafficLight.RED else -1
            self.last_wp = light_wp
            self.upcoming_red_light_pub.publish(Int32(light_wp))
        else:
            self.upcoming_red_light_pub.publish(Int32(self.last_wp))
        self.state_count += 1

    def get_closest_light(self, pose, lights):
        """Identifies the closest traffic light, if any
        Args:
            pose (Pose): current position of the car
            lights (TrafficLights): reported lights

        Returns:
            Traffic light or None

        """
        if pose is None:
            return None

        if lights is None:
            return None

        quaternion = (pose.pose.orientation.x, pose.pose.orientation.y,
                      pose.pose.orientation.z, pose.pose.orientation.w)
        # https://answers.ros.org/question/69754/quaternion-transformations-in-python/
        euler_orientation = tf.transformations.euler_from_quaternion(quaternion)
        # roll = euler_orientation[0]
        # pitch = euler_orientation[1]
        yaw = euler_orientation[2]

        def dist(p1, p2):
            return math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2)

        result = None
        best_distance = None

        for i in range(len(lights)):
            distance = dist(pose.pose.position, lights[i].pose.pose.position)
            # rospy.loginfo('Distance is %f' % distance)

            if best_distance is not None:
                if distance > best_distance:
                    continue

            if (distance < MAX_LIGHTS_DISTANCE) and (distance > MIN_LIGHTS_DISTANCE):
                heading = math.atan2(
                    (lights[i].pose.pose.position.y - pose.pose.position.y),
                    (lights[i].pose.pose.position.x - pose.pose.position.x))
                angle = abs(yaw - heading)
                # rospy.loginfo('Angle is %f' % angle)
                if angle < math.pi / 9:
                    best_distance = distance
                    result = lights[i]

        return result


    def get_closest_waypoint(self, pose):
        """Identifies the closest path waypoint to the given position
            https://en.wikipedia.org/wiki/Closest_pair_of_points_problem
        Args:
            pose (Pose): position to match a waypoint to

        Returns:
            int: index of the closest waypoint in self.waypoints

        """
        #TODO implement
        return 0

    def get_light_state(self, light):
        """Determines the current color of the traffic light

        Args:
            light (TrafficLight): light to classify

        Returns:
            int: ID of traffic light color (specified in styx_msgs/TrafficLight)

        """
        if(not self.has_image):
            self.prev_light_loc = None
            return False

        cv_image = self.bridge.imgmsg_to_cv2(self.camera_image, "bgr8")

        #Get classification
        return self.light_classifier.get_classification(cv_image)

    def process_traffic_lights(self):
        """Finds closest visible traffic light, if one exists, and determines its
            location and color

        Returns:
            int: index of waypoint closes to the upcoming stop line for a traffic light (-1 if none exists)
            int: ID of traffic light color (specified in styx_msgs/TrafficLight)

        """
        light = None

        # List of positions that correspond to the line to stop in front of for a given intersection
        stop_line_positions = self.config['stop_line_positions']
        if(self.pose):
            car_position = self.get_closest_waypoint(self.pose.pose)

        #TODO find the closest visible traffic light (if one exists)

        if light:
            state = self.get_light_state(light)
            return light_wp, state
        self.waypoints = None
        return -1, TrafficLight.UNKNOWN

if __name__ == '__main__':
    try:
        TLDetector()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start traffic node.')
