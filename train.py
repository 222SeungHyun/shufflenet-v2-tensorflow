import tensorflow as tf
import os
from model import model_fn, RestoreMovingAverageHook
from input_pipeline import Pipeline
tf.logging.set_verbosity('INFO')


"""
The purpose of this script is to train a network.
Evaluation will happen periodically.

To use it just run:
python train.py
"""

GPU_TO_USE = '0'
BATCH_SIZE = 32  # per gpu
NUM_EPOCHS = 5
TRAIN_DATASET_SIZE = 123123123124
NUM_GPUS = 1
PARAMS = {
    'train_dataset_path': '/mnt/datasets/imagenet/train_shards/',
    'val_dataset_path': '/mnt/datasets/imagenet/val_shards/',
    'weight_decay': 4e-5,
    'initial_learning_rate': 0.5,
    'decay_steps': (TRAIN_DATASET_SIZE * NUM_EPOCHS) // BATCH_SIZE,
    'end_learning_rate': 1e-6,
}


def get_input_fn(is_training):

    dataset_path = params['train_dataset_path'] if is_training else params['val_dataset_path']
    filenames = os.listdir(dataset_path)
    filenames = [n for n in filenames if n.endswith('.tfrecords')]
    filenames = [os.path.join(dataset_path, n) for n in sorted(filenames)]

    def input_fn():
        pipeline = Pipeline(
            filenames, is_training, batch_size=BATCH_SIZE,
            num_epochs=NUM_EPOCHS, num_gpus=NUM_GPUS
        )
        return pipeline.dataset

    return input_fn


session_config = tf.ConfigProto(
    inter_op_parallelism_threads=0,
    intra_op_parallelism_threads=0,
    allow_soft_placement=True
)
session_config.gpu_options.visible_device_list = '0,1'
distribution = tf.contrib.distribute.MirroredStrategy(num_gpus=2)
distribution = tf.contrib.distribute.OneDeviceStrategy('device:GPU:{}'.format(GPU_TO_USE))
run_config = tf.estimator.RunConfig(train_distribute=distribution)
run_config = run_config.replace(
    model_dir=params['model_dir'], session_config=session_config,
    save_summary_steps=500, save_checkpoints_secs=1200,
    log_step_count_steps=500
)

train_input_fn = get_input_fn(is_training=True)
val_input_fn = get_input_fn(is_training=False)
estimator = tf.estimator.Estimator(model_fn, params=PARAMS, config=run_config)

train_spec = tf.estimator.TrainSpec(train_input_fn, max_steps=PARAMS['num_steps'])
eval_spec = tf.estimator.EvalSpec(
    val_input_fn, steps=None, start_delay_secs=3600 * 3, throttle_secs=3600 * 3,
    hooks=[RestoreMovingAverageHook(PARAMS['model_dir'])]
)
tf.estimator.train_and_evaluate(estimator, train_spec, eval_spec)