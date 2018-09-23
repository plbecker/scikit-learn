"""
===================================================
Self-training: Comparing performance
===================================================
This example demonstrates the performance of the SelfTrainingClassifier.

The digits dataset is loaded, and a SVC classifier is created. Then, a
SelfTrainingClassifier is initialised, using the same SVC as its
base estimator.

The dataset contains 1797 data points, and the SelfTrainingClassifier is
trained using all 1797 data points, of which some are unlabeled. The normal SVC
is trained using only the labeled data points.

The graph shows that the SelfTrainingClassifier outperforms the normal SVC
when only few labeled data points are available.

This example extends the
:ref:`sphx_glr_auto_examples_classification_plot_digits_classification.py`
example.
"""
# Authors: Oliver Rausch    <oliverrausch99@gmail.com>
#          Patrice Becker   <beckerp@ethz.ch>
# License: BSD 3 clause
print(__doc__)
import numpy as np
import matplotlib.pyplot as plt
from sklearn.semi_supervised.self_training import SelfTrainingClassifier
from sklearn.utils import shuffle
from sklearn.svm import SVC
from sklearn.datasets import load_digits
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score

supervised_score = []
self_training_score = []
x_values = []

clf = SVC(probability=True, gamma=0.001)
self_training_clf = SelfTrainingClassifier(clf, max_iter=10, threshold=0.8)

X, y = load_digits(return_X_y=True)
X, y = shuffle(X, y, random_state=42)
y_true = y.copy()
for t in range(1000, 0, -250):
    x_values.append(t)

    lim = t
    y[lim:] = -1

    supervised_score_temp = []
    self_training_score_temp = []

    skfolds = StratifiedKFold(n_splits=3, random_state=42)
    for train_index, test_index in skfolds.split(X, y):
        X_train = X[train_index]
        y_train = y[train_index]
        X_test = X[test_index]
        y_test = y[test_index]
        y_test_true = y_true[test_index]

        X_train_filtered = X_train[np.where(y_train != -1)]
        y_train_filtered = y_train[np.where(y_train != -1)]

        clf.fit(X_train_filtered, y_train_filtered)
        y_pred = clf.predict(X_test)
        supervised_score_temp.append(f1_score(y_test_true,
                                              y_pred,
                                              average='macro'))

        self_training_clf.fit(X_train, y_train)
        y_pred = self_training_clf.predict(X_test)
        self_training_score_temp.append(f1_score(y_test_true,
                                                 y_pred,
                                                 average='macro'))

    supervised_score.append(np.array(supervised_score_temp).mean())
    self_training_score.append(np.array(self_training_score_temp).mean())

plt.figure(1)
plt.plot(x_values, supervised_score, label='Supervised (SVC)')
plt.plot(x_values, self_training_score,
         label='SelfTrainingClassifier using SVC')
plt.legend()
plt.ylabel("f1_score (macro average)")
plt.title("Comparison of classifiers on limited labeled data")
plt.xlabel("Amount of labeled data")
plt.show()
