import numpy as np
import json
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()

with open('config.json') as config_file:
    config = json.load(config_file)

def get_loss(model, args):
    loss = model.xent
    if args.robust and not args.stable:
        loss = model.robust_xent
    if args.MC:
        assert(not args.robust)
        loss = model.MC_xent
    elif args.stable:
        if args.robust:
            loss = model.robust_stable_xent
        else:
            loss = model.dual_xent

    return loss


def create_dict(args, num_classes, train_shape, test_size):
    dict_exp = {}
    dict_exp['logits_acc'] = np.zeros((config['num_experiments'], test_size[0], num_classes))
    dict_exp['W1_acc'] = np.zeros((config['num_experiments'], train_shape[1] * args.l1_size))
    dict_exp['W2_acc'] = np.zeros((config['num_experiments'], args.l1_size * args.l2_size))
    dict_exp['W3_acc'] = np.zeros((config['num_experiments'], args.l2_size * num_classes))
    dict_exp['b1_acc'] = np.zeros((config['num_experiments'], args.l1_size))
    dict_exp['b2_acc'] = np.zeros((config['num_experiments'], args.l2_size))
    dict_exp['b3_acc'] = np.zeros((config['num_experiments'], num_classes))
    dict_exp['log_a1']= np.zeros((config['num_experiments'], train_shape[1] * args.l1_size))
    dict_exp['log_a2'] = np.zeros((config['num_experiments'], args.l1_size * args.l2_size))
    dict_exp['log_a3'] = np.zeros((config['num_experiments'], args.l2_size * num_classes))
    dict_exp['preds'] = np.zeros((config['num_experiments'], test_size[0]))
    dict_exp['test_accs'] = np.zeros(config['num_experiments'])
    dict_exp['thetas'] = np.zeros(config['num_experiments'])
    dict_exp['iterations'] = np.zeros(config['num_experiments'])
    dict_exp['W1_non_zero'] = np.zeros(config['num_experiments'])
    dict_exp['W2_non_zero'] = np.zeros(config['num_experiments'])
    dict_exp['W3_non_zero'] = np.zeros(config['num_experiments'])
    dict_exp['W1_killed_input_features'] = 0
    dict_exp['W1_killed_neurons'] = 0
    dict_exp['W2_killed_input_features'] = 0
    dict_exp['W2_killed_neurons'] = 0
    dict_exp['W3_killed_input_features'] = 0
    dict_exp['W3_killed_neurons'] = 0
    dict_exp['adv_test_accs'] = {eps_test: np.zeros(config['num_experiments']) for eps_test in args.robust_test}

    return dict_exp


def update_dict(dict_exp, args, sess, model, test_dict, experiment):

    dict_exp['thetas'][experiment] = sess.run(model.theta)

    if args.model == "ff":
        dict_exp['b1_acc'][experiment] = sess.run(model.b1)
        dict_exp['b2_acc'][experiment] = sess.run(model.b2)
        dict_exp['b3_acc'][experiment] = sess.run(model.b3)
        dict_exp['log_a1'][experiment] = sess.run(model.log_a_W1).reshape(-1)
        dict_exp['log_a2'][experiment] = sess.run(model.log_a_W2).reshape(-1)
        dict_exp['log_a3'][experiment] = sess.run(model.log_a_W3).reshape(-1)

        if args.l0 > 0:
            dict_exp['W1_non_zero'] = sum(sess.run(model.W1_masked).reshape(-1) > 0) / sess.run(model.W1_masked).reshape(-1).shape[0]
            dict_exp['W2_non_zero'] = sum(sess.run(model.W2_masked).reshape(-1) > 0) / sess.run(model.W2_masked).reshape(-1).shape[0]
            dict_exp['W3_non_zero'] = sum(sess.run(model.W3_masked).reshape(-1) > 0) / sess.run(model.W3_masked).reshape(-1).shape[0]
            dict_exp['W1_killed_neurons'] = sum(np.sum(sess.run(model.W1_masked), axis=0) == 0)
            dict_exp['W1_killed_input_features'] = sum(np.sum(sess.run(model.W1_masked), axis=1) == 0)  # sum(np.sum(sess.run(model.W1_masked), axis= 1) == 0))
            dict_exp['W2_killed_neurons'] = sum(np.sum(sess.run(model.W2_masked), axis=0) == 0)
            dict_exp['W2_killed_input_features'] = sum(np.sum(sess.run(model.W2_masked), axis=1) == 0)
            dict_exp['W3_killed_neurons'] = sum(np.sum(sess.run(model.W3_masked), axis=0) == 0)
            dict_exp['W3_killed_input_features'] = sum(np.sum(sess.run(model.W3_masked), axis=1) == 0)
            dict_exp['W1_acc'][experiment] = sess.run(model.W1_masked).reshape(-1)
            dict_exp['W2_acc'][experiment] = sess.run(model.W2_masked).reshape(-1)
            dict_exp['W3_acc'][experiment] = sess.run(model.W3_masked).reshape(-1)
        else:
            dict_exp['W1_acc'][experiment] = sess.run(model.W1).reshape(-1)
            dict_exp['W2_acc'][experiment] = sess.run(model.W2).reshape(-1)
            dict_exp['W3_acc'][experiment] = sess.run(model.W3).reshape(-1)
            dict_exp['W1_non_zero'] = sum(sess.run(model.W1).reshape(-1) > 0) / sess.run(model.W1).reshape(-1).shape[0]
            dict_exp['W2_non_zero'] = sum(sess.run(model.W2).reshape(-1) > 0) / sess.run(model.W2).reshape(-1).shape[0]
            dict_exp['W3_non_zero'] = sum(sess.run(model.W3).reshape(-1) > 0) / sess.run(model.W3).reshape(-1).shape[0]

    dict_exp['logits_acc'][experiment] = sess.run(model.logits, feed_dict=test_dict)
    dict_exp['preds'][experiment] = sess.run(model.y_pred, feed_dict=test_dict)


    return dict_exp

def get_best_model(dict_exp, experiment, args, num_classes, num_subsets, batch_size, subset_ratio, num_features, theta, num_channels, pixels_x, pixels_y):
    if args.model == "ff":
        W1, b1 = dict_exp['W1_acc'][experiment], dict_exp['b1_acc'][experiment]
        W2, b2 = dict_exp['W2_acc'][experiment], dict_exp['b2_acc'][experiment]
        W3, b3 = dict_exp['W3_acc'][experiment], dict_exp['b3_acc'][experiment]
        theta_val = dict_exp['thetas'][experiment]
        log_a1 = dict_exp['log_a1'][experiment] 
        log_a2 = dict_exp['log_a2'][experiment] 
        log_a3 = dict_exp['log_a3'][experiment]

        from NN_model import Model
        W = [[W1, b1], [W2, b2], [W3, b3], theta_val, [log_a1, log_a2, log_a3]]
        best_model = Model(num_classes, num_subsets, batch_size, args.l1_size, args.l2_size, subset_ratio, num_features, args.dropout, args.l2, args.l0, args.robust, args.reg_stability, W)
        return best_model

