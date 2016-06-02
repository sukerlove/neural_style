import os, json, gc, argparse
import numpy as np

from keras import backend as K
from keras.engine.training import collect_trainable_weights
from keras.optimizers import Adam
# from keras.utils.visualize_util import plot as plot_model

from vgg19.model_headless import VGG_19_headless_5, get_layer_data
from models.style_transfer import (style_transfer_conv_transpose)

from utils.imutils import plot_losses, load_image, load_mean
from utils.lossutils import (grams, frobenius_error, 
                    train_weights, total_variation_error)

dir = os.path.dirname(os.path.realpath(__file__))
vgg19Dir = dir + '/vgg19'
dataDir = dir + '/data'
resultsDir = dataDir + '/output'
if not os.path.isdir(resultsDir): 
    os.makedirs(resultsDir)
trainDir = dataDir + '/train'
overfitDir = dataDir + '/overfit'
paintingsDir = dataDir + '/paintings'

channels = 3
width = 512
height = 512
input_shape = (channels, width, height)
batch_size = 2

parser = argparse.ArgumentParser(
    description='Neural artistic style. Generates an image by combining '
                'the content of an image and the style of another.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('--style', default=dataDir + '/paintings/edvard_munch-the_scream.jpg', type=str, help='Style image.')
parser.add_argument('--pooling_type', default='max', type=str, choices=['max', 'avg'], help='Subsampling scheme.')
args = parser.parse_args()

X_train_style = np.array([load_image(args.style, size=(height, width), dim_ordering='th', verbose=True)])
print("X_train_style shape:", X_train_style.shape)

print('Loading style_transfer model')
stWeightsFullpath = dir + '/models/st_vangogh_weights.hdf5'

st_model = style_transfer_conv_transpose(input_shape=input_shape) # th ordering, BGR
if os.path.isfile(stWeightsFullpath): 
    print("Loading weights")
    st_model.load_weights(stWeightsFullpath)
init_weights = st_model.get_weights()
# plot_model(st_model, to_file=dir + '/st_model.png', show_shapes=True)

print('Loading VGG headless 5')
modelWeights = vgg19Dir + '/vgg-19_headless_5_weights.hdf5'
vgg_model = VGG_19_headless_5(modelWeights, trainable=False, pooling_type='max')
layer_dict, layers_names = get_layer_data(vgg_model, 'conv_')
print('Layers found:' + ', '.join(layers_names))

print('Creating training labels')
style_layers_used = ['conv_1_2', 'conv_2_2', 'conv_3_2', 'conv_3_4', 'conv_4_3']
style_outputs_layer = [grams(layer_dict[name].output) for name in style_layers_used]
predict_style = K.function([vgg_model.input], style_outputs_layer)
y_styles = predict_style([X_train_style]) # sub mean, th ordering, BGR

mean = load_mean(name='vgg19', dim_ordering='th') # th ordering, BGR
vgg_content_input = st_model.input - mean # th, BGR ordering, sub mean
[c11, c12, 
c21, c22, 
c31, c32, c33, c34, 
c41, c42, c43, c44,
c51, c52, c53, c54] = vgg_model(vgg_content_input)
y_feat = c42

print('Building full model')
preprocessed_output = st_model.output - mean # th, BGR ordering, sub mean
[fm_c11, fm_c12, 
fm_c21, fm_c22, 
fm_c31, fm_c32, fm_c33, fm_c34,
fm_c41, fm_c42, fm_c43, fm_c44,
fm_c51, fm_c52, fm_c53, fm_c54] = vgg_model(preprocessed_output)
preds = [fm_c11, fm_c12, fm_c21, fm_c22, fm_c31, fm_c32, fm_c33, fm_c34, fm_c41, fm_c42, fm_c43, fm_c44, fm_c51, fm_c52, fm_c53, fm_c54]
pred_styles = [fm_c12, fm_c22, fm_c32, fm_c34, fm_c43]
pred_feat = fm_c42

print('Preparing training loss functions')
train_loss_styles = []
for idx, y_style in enumerate(y_styles):
    train_loss_styles.append(
        frobenius_error(
            y_style, 
            grams(pred_styles[idx])
        )
    )

train_loss_feat = frobenius_error(y_feat, pred_feat)

reg_TV = total_variation_error(preprocessed_output, 2)

print('Iterating over hyper parameters')
current_iter = 0
for alpha in [20e0]:
    for beta in [1.]:
        for gamma in [1e-04]:
            print("alpha, beta, gamma:", alpha, beta, gamma)

            gc.collect()
        
            st_model.set_weights(init_weights)
            print('Compiling train loss')
            tls = [train_loss_style * alpha * 1 / len(train_loss_styles) for train_loss_style in train_loss_styles]
            tlf = [train_loss_feat * beta]
            rtv = reg_TV * gamma
            train_loss =  sum(tls + tlf) + rtv

            print('Compiling Adam update')
            adam = Adam(lr=1e-02)
            updates = adam.get_updates(collect_trainable_weights(st_model), st_model.constraints, train_loss)

            print('Compiling train function')
            inputs = [st_model.input, K.learning_phase()]
            outputs = [train_loss] + tlf + tls
            train_iteratee = K.function(inputs, outputs, updates=updates)

            print('Starting training')
            weights, losses = train_weights(
                trainDir,
                # overfitDir, 
                (height, width),
                st_model, 
                train_iteratee, 
                cv_input_dir=None, 
                max_iter=4000,
                batch_size=batch_size
            )

            best_trainable_weights = weights[0]
            last_trainable_weights = weights[1]
            prefix = str(current_iter).zfill(4)
            suffix = '_alpha' + str(alpha) +'_beta' + str(beta) + '_gamma' + str(gamma)
            best_st_weights = resultsDir + '/' + prefix + 'best_st_vangogh_weights' + suffix + '.hdf5'
            last_st_weights = resultsDir + '/' + prefix + 'last_st_vangogh_weights' + suffix + '.hdf5'
            fullpath_loss = resultsDir + '/' + prefix + 'st_vangogh_loss' + suffix + '.json'
            current_iter += 1

            print("Saving final data")
            st_model.set_weights(best_trainable_weights)
            st_model.save_weights(best_st_weights, overwrite=True)
            st_model.set_weights(last_trainable_weights)
            st_model.save_weights(last_st_weights, overwrite=True)

            with open(fullpath_loss, 'w') as outfile:
                json.dump(losses, outfile)  

            plot_losses(losses, resultsDir, prefix, suffix)
