#!/bin/python

import glob
import cv2
import numpy as np
import pandas as pd
from keras.applications.mobilenet import preprocess_input as mobilenet_preprocess_input
from sklearn.model_selection import train_test_split

from mach.util import full_path
# from util import full_path


def raw_train_data():
	image_path = full_path("data/orig/train/*.png")
	num_images = len(glob.glob(image_path))
	# glob does not return image files in correct order!!!!!
	image_files = [full_path("data/orig/train/frame_{}.png".format(i)) for i in range(num_images)]
	label_path = "video_data/train.txt"
	train_labels = read_txt_file(label_path)[0:num_images]

	return (image_files, train_labels)

def raw_test_data():
	image_path = full_path("data/orig/test/*.png")
	num_images = len(glob.glob(image_path))
	# glob does not return image files in correct order!!!!!
	image_files = [full_path("data/orig/test/frame_{}.png".format(i)) for i in range(num_images)]

	return image_files

def read_txt_file(file_path):
	with open(full_path(file_path), "r") as f:
		return np.array(list(map(float, f)))

def img_from_file(file):
  img = cv2.imread(file)
  return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

### Augmentation functions
CROP_SIZE = (134,330,32,608)
IMAGE_SIZE = (288, 98) # divisable by 32 for MobileNet

def crop_resize_images(images):
	fn = lambda i: crop_resize_image(i, CROP_SIZE, IMAGE_SIZE)
	return map(fn, images)

def crop_resize_image(image, crop_size, image_size):	
	image = crop_image(image,crop_size)
	return cv2.resize(image, image_size, interpolation=cv2.INTER_NEAREST)

# augment a group of images with the same values
def augment_images(images):
	brightness_min = 0.7
	brightness_max = 1.25
	brightness = np.random.uniform(brightness_min, brightness_max)
	translation_x_min = -20
	translation_x_max = 20
	translation_y_min = -20
	translation_y_max = 20
	translation_x = np.random.uniform(translation_x_min, translation_x_max)
	translation_y = np.random.uniform(translation_y_min, translation_y_max)
	scale_x1_min = 0
	scale_x2_min = 0
	scale_y1_min = 0
	scale_y2_min = 0
	scale_x1_max = 20
	scale_x2_max = 20
	scale_y1_max = 20
	scale_y2_max = 20
	scale_x1 = np.random.uniform(scale_x1_min, scale_x1_max)
	scale_x2 = np.random.uniform(scale_x2_min, scale_x2_max)
	scale_y1 = np.random.uniform(scale_y1_min, scale_y1_max)
	scale_y2 = np.random.uniform(scale_y2_min, scale_y2_max)

	fn = lambda image: augment_image(image, brightness, translation_x, translation_y, scale_x1, scale_x2, scale_y1, scale_y2)

	return list(map(fn, images))

def augment_image(image, brightness, translation_x, translation_y, scale_x1, scale_x2, scale_y1, scale_y2):
	image = augment_image_brightness(image, brightness)
	image = translate_image(image, translation_x, translation_y)
	return stretch_image(image, scale_x1, scale_x2, scale_y1, scale_y2)

def crop_image(image, crop_size):
	x1, x2, y1, y2 = crop_size
	return image[x1:x2, y1:y2]

def augment_image_brightness(image, brightness):
	### Augment brightness
	image1 = np.float32(cv2.cvtColor(image,cv2.COLOR_RGB2HSV))
	image1[:,:,2] = image1[:,:,2]*brightness
	image1 = np.uint8(np.clip(image1, 0., 255.))
	return cv2.cvtColor(image1,cv2.COLOR_HSV2RGB)

def translate_image(image, translation_x, translation_y):
	# Translation augmentation
	Trans_M = np.float32([[1,0,translation_x],[0,1,translation_y]])
	rows,cols,channels = image.shape
	return cv2.warpAffine(image,Trans_M,(cols,rows))

def stretch_image(image,scale_x1,scale_x2,scale_y1,scale_y2):
	# Stretching augmentation
	p1 = (scale_x1,scale_y1)
	p2 = (image.shape[1]-scale_x2,scale_y1)
	p3 = (image.shape[1]-scale_x2,image.shape[0]-scale_y2)
	p4 = (scale_x1,image.shape[0]-scale_y2)

	pts1 = np.float32([[p1[0],p1[1]],
	               [p2[0],p2[1]],
	               [p3[0],p3[1]],
	               [p4[0],p4[1]]])
	pts2 = np.float32([[0,0],
	               [image.shape[1],0],
	               [image.shape[1],image.shape[0]],
	               [0,image.shape[0]]])

	M = cv2.getPerspectiveTransform(pts1,pts2)
	image = cv2.warpPerspective(image,M,(image.shape[1],image.shape[0]))
	return np.array(image,dtype=np.uint8)


def average_optical_flow_dense(images):
	"""
	input: images (RGB images) assumed to be in time sequence order
	* calculates optical flow magnitude and angle and places it into HSV image
	* Set the saturation to the saturation value of image_next
	* Set the hue to the angles returned from computing the flow params
	* set the value to the magnitude returned from computing the flow params
	* Convert from HSV to RGB and return RGB image with same size as original image
	"""
	assert(len(images) > 1)

	to_gray = lambda image: cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
	gray_images = list(map(to_gray, images))
	result = []

	for i in range(len(gray_images) - 1):
		old = gray_images[i]
		new = gray_images[i+1]
		result.append(single_optical_flow_dense(old, new))

	return np.mean(result, axis=0)

def single_optical_flow_dense(old_image_gray, current_image_gray):
	"""
	input: old_image_gray, current_image_gray (gray images)
	* calculates optical flow magnitude and angle and places it into HSV image
	* Set the hue to the angles returned from computing the flow params
	* set the value to the magnitude returned from computing the flow params
	* Convert from HSV to RGB and return RGB image with same size as original image
	"""
	# Flow Parameters
	# flow = None
	pyr_scale = 0.5
	levels = 1
	winsize = 12
	iterations = 2
	poly_n = 5
	poly_sigma = 1.3
	extra = 0
	# obtain dense optical flow paramters
	# https://github.com/npinto/opencv/blob/master/samples/python2/opt_flow.py
	# http://docs.opencv.org/trunk/d7/d8b/tutorial_py_lucas_kanade.html
	flow = cv2.calcOpticalFlowFarneback(old_image_gray, current_image_gray,  
																			None, #flow_mat 
																			pyr_scale, 
																			levels, 
																			winsize, 
																			iterations, 
																			poly_n, 
																			poly_sigma, 
																			extra)

	return flow_to_rgb(flow)


def flow_to_rgb(flow):
	h, w = flow.shape[:2]
	fx, fy = flow[:,:,0], flow[:,:,1]
	ang = np.arctan2(fy, fx) + np.pi
	v = np.sqrt(fx*fx+fy*fy)
	hsv = np.zeros((h, w, 3), np.uint8)
	hsv[...,0] = ang*(180/np.pi/2)
	hsv[...,1] = 255
	hsv[...,2] = np.minimum(v*4, 255)
	rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
	return rgb

def create_optical_flow_data(num_images, num_augmentations, file_path, is_test, is_train_full):
	if is_test:
		create_optical_flow_data_full(num_images, num_augmentations, "{}/test".format(file_path), raw_test_data())
	elif is_train_full:
		create_optical_flow_data_full(num_images, num_augmentations, "{}/train_full".format(file_path), raw_train_data()[0])
	else:
		create_optical_flow_data_train(num_images, num_augmentations, file_path)

def create_optical_flow_data_full(num_images, num_augmentations, file_path, files):
	results = []
	print("Processing a total of {} images.".format(len(files)))
	for i in range(len(files)-num_images+1):
		if i % 100 == 0: print("Finished with {} original images.".format(i))

		files_batch = files[i:i+num_images]
		images = list(map(img_from_file, files_batch))
		flow = list(crop_resize_images([average_optical_flow_dense(images)]))[0]
			
		flow_file_path = "{}/flow_{}_{}.png".format(file_path, i, i+num_images)
		results.append(flow_file_path)
		cv2.imwrite(flow_file_path, flow)
	pd.DataFrame(results, columns=['flow_path']).to_csv("{}/files_labels.csv".format(file_path))

def create_optical_flow_data_train(num_images, num_augmentations, file_path, valid_pct=0.3):
	train_files, train_labels = raw_train_data()
	end = ((len(train_labels) // num_images - 1) * num_images)
	train_results = []
	valid_results = []
	print("Processing a total of {} images.".format(len(train_labels)))

	for i in range(0, end, num_images):
		speed = train_labels[i+num_images-1]
		if i % 100 == 0: print("Finished with {} original images.".format(i))

		if np.random.uniform() < valid_pct:
			files = train_files[i:i+num_images]
			valid_images = list(map(img_from_file, files))
			flow = list(crop_resize_images([average_optical_flow_dense(valid_images)]))[0]
			valid_images = list(crop_resize_images(valid_images))
			flow_file_path = "{}/valid/flow_{}_{}.png".format(file_path, i, i+num_images)
			cv2.imwrite(flow_file_path, flow)
			img_file_paths = []
			for img_i in range(len(valid_images)):
				img_file_path = "{}/valid/frame_{}.png".format(file_path, i+img_i)
				img_file_paths.append(img_file_path)
				cv2.imwrite(img_file_path, valid_images[img_i])

			row = [flow_file_path, speed] + img_file_paths
			valid_results.append(row)	

		else:
			for j in range(num_augmentations):
				aug_imgs = list(augment_images(map(img_from_file, train_files[i:i+num_images])))
				flow = list(crop_resize_images([average_optical_flow_dense(aug_imgs)]))[0]
				aug_imgs = list(crop_resize_images(aug_imgs))
				flow_file_path = "{}/train/flow_{}_{}_aug_{}.png".format(file_path, i, i+num_images, j)
				cv2.imwrite(flow_file_path, flow)
				aug_file_paths = []
				for img_i in range(len(aug_imgs)):
					aug_file_path = "{}/train/frame_{}_aug_{}.png".format(file_path, i+img_i, j)
					aug_file_paths.append(aug_file_path)
					cv2.imwrite(aug_file_path, aug_imgs[img_i])

				row = [flow_file_path, speed] + aug_file_paths
				train_results.append(row)

	columns = ["flow_path", "speed"] + ["frame_{}".format(i) for i in range(num_images)]
	pd.DataFrame(train_results, columns=columns).to_csv("{}/train/files_labels.csv".format(file_path))
	pd.DataFrame(valid_results, columns=columns).to_csv("{}/valid/files_labels.csv".format(file_path))


def create_optical_flow_data_recurrent(file_path):
	train_files, train_labels = raw_train_data()
	results = []
	print("Processing a total of {} images.".format(len(train_labels)))

	for i in range(1, len(train_labels)):
		speed = train_labels[i]
		if i % 100 == 0: print("Finished with {} original images.".format(i))

		imgs = list(map(img_from_file, train_files[i-1:i+1]))
		flow = list(crop_resize_images([average_optical_flow_dense(imgs)]))[0]
		flow_file_path = "{}/flow_{}.png".format(file_path, i)
		cv2.imwrite(flow_file_path, flow)
		row = [flow_file_path, speed]
		results.append(row)

	columns = ["flow_path", "speed"]
	pd.DataFrame(results, columns=columns).to_csv("{}/files_labels.csv".format(file_path))


def create_orig_recurrent_generator(batch_size, sequence_size, is_debug):
	image_files, labels = raw_train_data()
	image_files = np.array(image_files)
	if is_debug:
		end = min(len(image_files), 1024)
		image_files = image_files[0:end]
		labels = labels[0:end]

	recurrent_idxs = np.array([i for i in range(0, len(image_files)-sequence_size, sequence_size // 2)])
	train_idxs, valid_idxs, _, _ = train_test_split(recurrent_idxs, recurrent_idxs, test_size=0.30, random_state=42)

	train = (len(train_idxs) // batch_size, OrigRecurrentGenerator(image_files, labels, train_idxs, batch_size, sequence_size))
	valid = (len(valid_idxs) // batch_size, OrigRecurrentGenerator(image_files, labels, valid_idxs, batch_size, sequence_size))
	return train, valid, train[1].next()[0].shape[2:]

class OrigRecurrentGenerator():
	def __init__(self, image_files, labels, idxs, batch_size, sequence_size):
		self.image_files = image_files
		self.labels = labels
		self.idxs = idxs
		self.batch_size = batch_size
		self.sequence_size = sequence_size

	def __next__(self):
		return self.next()

	def next(self):
		start_idxs = self.idxs[np.random.randint(0, len(self.idxs), self.batch_size)]
		labels = self.labels[start_idxs + self.sequence_size - 1]
		images = np.array([orig_recurrent_sequence(i, self.image_files, self.sequence_size) for i in start_idxs])

		return (images, labels)

def orig_recurrent_sequence(idx, image_files, sequence_size):
	images = preprocess_valid_images(map(img_from_file, image_files[idx:idx+sequence_size]))
	return mobilenet_preprocessor(images)


def create_recurrent_generators(folder_path, batch_size, sequence_size, is_debug):
	df = pd.read_csv("{}/files_labels.csv".format(folder_path))
	if is_debug:
		end = min(len(df), 1024)
		df = df[0:end]

	recurrent_idxs = np.array([i for i in range(0, len(df)-sequence_size, sequence_size // 2)])
	train_idxs, valid_idxs, _, _ = train_test_split(recurrent_idxs, recurrent_idxs, test_size=0.30, random_state=42)

	train = (len(train_idxs) // batch_size, RecurrentGenerator(df, train_idxs, batch_size, sequence_size))
	valid = (len(valid_idxs) // batch_size, RecurrentGenerator(df, valid_idxs, batch_size, sequence_size))
	return train, valid, train[1].next()[0].shape[2:]

class RecurrentGenerator():
	def __init__(self, df, idxs, batch_size, sequence_size):
		self.df = df
		self.idxs = idxs
		self.batch_size = batch_size
		self.sequence_size = sequence_size

	def __next__(self):
		return self.next()

	def next(self):
		start_idxs = self.idxs[np.random.randint(0, len(self.idxs), self.batch_size)]
		labels = self.df['speed'][start_idxs + self.sequence_size - 1]
		images = np.array([recurrent_sequence(i, self.df, self.sequence_size) for i in start_idxs])

		return (images, labels)

def recurrent_sequence(idx, df, sequence_size):
	return mobilenet_preprocessor(map(img_from_file, df['flow_path'][idx:idx+sequence_size]))

def create_mobilenet_full_generator(folder_path, is_debug):
	df = pd.read_csv("{}/files_labels.csv".format(folder_path))
	if is_debug:
		end = min(len(df), 1024)
		df = df[0:end]
	flow_paths = df['flow_path']
	return len(df), MobilenetFullGenerator(flow_paths)

class MobilenetFullGenerator():
	def __init__(self, files):
		self.files = files
		self.i = -1

	def __next__(self):
		return self.next()

	def next(self):
		self.i += 1
		if self.i >= len(self.files):
			self.i = 0
		return mobilenet_preprocessor(map(img_from_file, [self.files[self.i]]))


def create_mobilenet_generators(folder_path, batch_size, num_images, is_debug):
	train = create_mobilenet_generator("{}/train".format(folder_path), batch_size, num_images, is_debug)
	valid = create_mobilenet_generator("{}/valid".format(folder_path), batch_size, num_images, is_debug)

	return (train, valid, image_shape(valid[1]))

def image_shape(generator):
	val = generator.next()[0]
	return val[list(val.keys())[0]].shape[1:]

def create_mobilenet_generator(folder_path, batch_size, num_images, is_debug):
	# Load csv and shuffle
	df = pd.read_csv("{}/files_labels.csv".format(folder_path)).sample(frac=1).reset_index(drop=True)
	if is_debug:
		end = min(len(df), 1024)
		df = df[0:end]

	flow_paths = df['flow_path']
	labels = df['speed']
	img_files = df[['frame_{}'.format(i) for i in range(num_images)]]
	
	g = ImageFileGenerator(batch_size, flow_paths, labels, img_files, mobilenet_preprocessor)
	return (len(flow_paths) // batch_size , g)

def mobilenet_preprocessor(images):
	map_images = map(mobilenet_preprocess_input, map(as_(np.float32), images))
	return np.array(list(map_images))

def as_(dtype):
	return lambda image: np.array(image, dtype=dtype)
	

class ImageFileGenerator():
	def __init__(self, batch_size, flow_files, labels, image_files, preprocessor):
		self.batch_size = batch_size
		self.flow_files = flow_files
		self.labels = labels
		self.image_files = image_files
		self.preprocessor = preprocessor

	def __next__(self):
		return self.next()

	def next(self):
		idxs = np.random.randint(0, len(self.labels), self.batch_size)
		batch_flow_images = self.preprocessor(map(img_from_file, self.flow_files[idxs]))
		batch_labels = self.labels[idxs]

		result = {'flow': batch_flow_images}

		for key in self.image_files.columns.values:
			images = map(img_from_file,self.image_files[key][idxs])
			# result[key] = np.concatenate([self.preprocessor(images), batch_flow_images], axis=3)
			result[key] = self.preprocessor(images)

		return (result, batch_labels)

