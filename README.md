### Predicting vehicle odometry from monocular video

In this project I attept to predict a vehicles current speed based on a video taken from a a single camera on a car's front dashboard. The training sequence is 20400 frames shot at 20 fps. Each frame has a speed (m/s) associated with it. The speeds are in a txt file. 

In addition to the video images, I generated optical flow images from pairs of images using openCVs Farneback dense optical flow function. Farneback optical flow calculates the angle and magnitude of change for each pixel in an image. Conceptually, I thought the angles and magnitudes would be a good predictor of speed given consistent image time steps. If the car is moving quickly, the angles and/or the magnitues should be larger than in situations where the car is moving slowly. There are inherently some problems with this assumption, namely it assumes everything else in the field of view isn't moving. For instance, if a car is driving slightly slower than the test vehicle, the optical flow magnitude in the pixels near the car will be smaller than pixels in parts of the image that are static. Similarly if a car is driving past in the opposite direction, the optical flow magnitue will be larger for the pixels near the car compared to pixels of static objects. To me this means that although optical flow is an extremly helpful metric for predicting vehicle speed, there may be situations where the flow actaully throws the car off. 

I tried training a few different types of models for this project but generally ran into one of two problems. Either that model failed to train well and got stuck around 60 MSE or the model severly overfit to the training data, producting a low training MSE but a large test MSE. I will go over the model architectures below, but its possible that optical flow may actually not be a great way to determine vehicle speed. 

The first model I tried as a simple 5 CNN 3 FCN network, trained from scratch on the optical flow images. This model failed to train the model past 60 MSE. Since this model failed to learn past a threshold, I decided to try a larger model. The second model I tried was the new MobileNet model with an alpha of 0.75 followed by 2 FCN layers. This model overfit to the training data and resulted in large MSE for the validation data. The MobileNet model is ment for a large diverse dataset which this video dataset is not. The model mat be too large, although it does have some desirable charicteristics like having few parameters and being able to train quickly. I decided to create a new shorter MobileNet model, MobileNetSlim, which is oly the first 8 CNN layers of MobileNet. Depending on how many augmented images I used, I was either able to get this model to overfit or get stuck near 60 MSE. I tried a model that used the imagenet weights of MobileNet to encode pairs of images and then trained a small net over this models concatenated. I tried an untrained MobileNet with an input of the two frames with the optical flow concated to each image. In another model I tried to combine the encoded image pair with an encoded optical flow image. No luck. The last thing I tried was a recurrent network on top of a smaller encoder network using either the original image pair or the optical flow images. 

In the process of working on this project I've read a few papers on predicting vehicle odometry and most seem to focus on prdicting camera pose changes between two frames. Although I havent attempted this yet, predicting camera pose changes seems like a good approach because speed can be broken down into f(change in camera pose)/change in time.

### Further areas of exploration
I'm either failing to fit a good model, or significatnly overfitting, is this because so much of the data is from the highway? Maybe more data would help.
Should I reformat the problem as a classifier? The speeds are between 0 and ~25 so 100 classes would get down to very decent accuracy. 
This is a video, does a stateful recurrent neural network make sense?
Normally adding dropout helps with over fitting but in this regression problem, it felt like dropout caused the model to never train past a certain point and even caused the test error it swing wildly at times. Is there a better way to prevent overfitting for regression problems?

