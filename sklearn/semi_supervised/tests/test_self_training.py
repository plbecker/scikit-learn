import numpy as np
import pytest
from io import StringIO
import sys

from sklearn.utils.testing import assert_array_equal
from sklearn.utils.testing import assert_equal
from sklearn.exceptions import NotFittedError, ConvergenceWarning
from sklearn.semi_supervised import SelfTrainingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn.datasets import load_iris, make_blobs
from sklearn.metrics import accuracy_score

# Author: Oliver Rausch <rauscho@ethz.ch>
# License: BSD 3 clause

# load the iris dataset and randomly permute it
iris = load_iris()
X_train, X_test, y_train, y_test = train_test_split(iris.data,
                                                    iris.target,
                                                    random_state=0)

n_labeled_samples = 50

y_train_missing_labels = y_train.copy()
y_train_missing_labels[n_labeled_samples:] = -1
mapping = {0: 'A', 1: 'B', 2: 'C', -1: '-1'}
y_train_missing_strings = np.vectorize(mapping.get)(
    y_train_missing_labels).astype(object)
y_train_missing_strings[y_train_missing_labels == -1] = -1


def test_missing_predict_proba():
    # Check that an error is thrown if predict_proba is not implemented
    base_classifier = SVC(probability=False, gamma='scale')
    self_training = SelfTrainingClassifier(base_classifier)

    with pytest.raises(ValueError, match=r"base_classifier \(SVC\) should"):
        self_training.fit(X_train, y_train_missing_labels)


def test_none_classifier():
    st = SelfTrainingClassifier(None)
    with pytest.raises(ValueError, match="base_classifier cannot be None"):
        st.fit(X_train, y_train_missing_labels)


@pytest.mark.parametrize("max_iter, threshold",
                         [(-1, 1.0), (-100, -2), (-10, 10)])
def test_invalid_params(max_iter, threshold):
    # Test negative iterations
    base_classifier = SVC(gamma="scale", probability=True)
    st = SelfTrainingClassifier(base_classifier, max_iter=max_iter)
    with pytest.raises(ValueError, match="max_iter must be >= 0 or None"):
        st.fit(X_train, y_train)

    base_classifier = SVC(gamma="scale", probability=True)
    st = SelfTrainingClassifier(base_classifier, threshold=threshold)
    with pytest.raises(ValueError, match="threshold must be in"):
        st.fit(X_train, y_train)


def test_invalid_early_stopping():
    base_classifier = SVC(gamma="scale", probability=True)
    st = SelfTrainingClassifier(base_classifier,
                                n_iter_no_change=-10)
    with pytest.raises(ValueError, match="n_iter_no_change must be"):
        st.fit(X_train, y_train)

    st = SelfTrainingClassifier(base_classifier, max_iter=5,
                                n_iter_no_change=10)

    with pytest.warns(UserWarning, match="early stopping is ineffective"):
        st.fit(X_train, y_train)


@pytest.mark.parametrize("base_classifier",
                         [KNeighborsClassifier(),
                          SVC(gamma="scale", probability=True,
                              random_state=0)])
def test_classification(base_classifier):
    # Check classification for various parameter settings.
    # Also assert that predictions for strings and numerical labels are equal.
    # Also test for multioutput classification
    threshold = 0.75
    max_iter = 10
    st = SelfTrainingClassifier(base_classifier, max_iter=max_iter,
                                threshold=threshold)
    st.fit(X_train, y_train_missing_labels)
    pred = st.predict(X_test)
    proba = st.predict_proba(X_test)

    st_string = SelfTrainingClassifier(base_classifier, max_iter=max_iter,
                                       threshold=threshold)
    st_string.fit(X_train, y_train_missing_strings)
    pred_string = st_string.predict(X_test)
    proba_string = st_string.predict_proba(X_test)

    assert_array_equal(np.vectorize(mapping.get)(pred), pred_string)
    assert_array_equal(proba, proba_string)

    assert st.termination_condition_ == st_string.termination_condition_
    # Check consistency between y_labeled_iter, n_iter and max_iter
    labeled = y_train_missing_labels != -1
    # assert that labeled samples have labeled_iter = 0
    assert_array_equal(st.labeled_iter_ == 0, labeled)
    # assert that labeled samples do not change label during training
    assert_array_equal(y_train_missing_labels[labeled],
                       st.transduction_[labeled])

    # assert that the max of the iterations is less than the total amount of
    # iterations
    assert np.max(st.labeled_iter_) <= st.n_iter_ <= max_iter
    assert np.max(st_string.labeled_iter_) <= st_string.n_iter_ <= max_iter

    # check shapes
    assert_equal(st.labeled_iter_.shape, st.transduction_.shape,
                 (n_labeled_samples,))
    assert_equal(st_string.labeled_iter_.shape, st_string.transduction_.shape,
                 (n_labeled_samples,))


def test_sanity_classification():
    base_classifier = SVC(gamma="scale", probability=True)
    base_classifier.fit(X_train[n_labeled_samples:],
                        y_train[n_labeled_samples:])

    st = SelfTrainingClassifier(base_classifier)
    st.fit(X_train, y_train_missing_labels)

    pred1, pred2 = base_classifier.predict(X_test), st.predict(X_test)
    assert not np.array_equal(pred1, pred2)
    score_supervised = accuracy_score(base_classifier.predict(X_test), y_test)
    score_self_training = accuracy_score(st.predict(X_test), y_test)

    assert score_self_training > score_supervised


def test_none_iter():
    # Check that the all samples were labeled after a 'reasonable' number of
    # iterations.
    st = SelfTrainingClassifier(KNeighborsClassifier(), threshold=.55,
                                max_iter=None)
    st.fit(X_train, y_train_missing_labels)

    assert st.n_iter_ < 10
    assert st.termination_condition_ == "all_labeled"


@pytest.mark.parametrize("base_classifier",
                         [KNeighborsClassifier(),
                          SVC(gamma="scale", probability=True,
                              random_state=0)])
@pytest.mark.parametrize("y", [y_train_missing_labels,
                               y_train_missing_strings])
def test_zero_iterations(base_classifier, y):
    # Check classification for zero iterations.
    # Fitting a SelfTrainingClassifier with zero iterations should give the
    # same results as fitting a supervised classifier.
    # This also asserts that string arrays work as expected.

    clf1 = SelfTrainingClassifier(base_classifier, max_iter=0)

    with pytest.warns(ConvergenceWarning, match="Maximum number of iterations"
                      " reached before early stopping"):
        clf1.fit(X_train, y)

    clf2 = base_classifier.fit(X_train[:n_labeled_samples],
                               y[:n_labeled_samples])

    assert_array_equal(clf1.predict(X_test), clf2.predict(X_test))
    assert clf1.termination_condition_ == "max_iter"


def test_notfitted():
    # Test that predicting without training throws an error
    st = SelfTrainingClassifier(KNeighborsClassifier())
    msg = "This SelfTrainingClassifier instance is not fitted yet"
    with pytest.raises(NotFittedError, match=msg):
        st.predict(X_train)
    with pytest.raises(NotFittedError, match=msg):
        st.predict_proba(X_train)


def test_prefitted_throws_error():
    # Test that passing a pre-fitted classifier and calling predict throws an
    # error
    knn = KNeighborsClassifier()
    knn.fit(X_train, y_train)
    st = SelfTrainingClassifier(knn)
    with pytest.raises(NotFittedError, match="This SelfTrainingClassifier"
                       " instance is not fitted yet"):
        st.predict(X_train)


@pytest.mark.parametrize("max_iter", range(1, 5))
def test_y_labeled_iter(max_iter):
    # Check that the amount of datapoints labeled in iteration 0 is equal to
    # the amount of labeled datapoints we passed.
    st = SelfTrainingClassifier(KNeighborsClassifier(), max_iter=max_iter,
                                n_iter_no_change=3)

    # If we look at the output for self.n_iter_ we can see that samples are
    # labeled only in iteration 1. Therefore early_stopping should only kick in
    # in iteration 5. This implies we fail to converge for max_iter < 4.
    with pytest.warns(ConvergenceWarning, match="Maximum number of iterations"
                      " reached before early stopping"):
        st.fit(X_train, y_train_missing_labels)
    amount_iter_0 = len(st.labeled_iter_[st.labeled_iter_ == 0])
    assert amount_iter_0 == n_labeled_samples
    # Check that the max of the iterations is less than the total amount of
    # iterations
    assert np.max(st.labeled_iter_) <= st.n_iter_ <= max_iter
    assert st.termination_condition_ == "max_iter"


def test_no_unlabeled():
    # Test that training on a fully labeled dataset produces the same results
    # as training the classifier by itself.
    knn = KNeighborsClassifier()
    knn.fit(X_train, y_train)
    st = SelfTrainingClassifier(knn)
    with pytest.warns(UserWarning, match="y contains no unlabeled samples"):
        st.fit(X_train, y_train)
    assert_array_equal(knn.predict(X_test), st.predict(X_test))
    # Assert that all samples were labeled in iteration 0 (since there were no
    # unlabeled samples).
    assert np.all(st.labeled_iter_ == 0)
    assert st.termination_condition_ == "all_labeled"


def test_early_stopping():
    # if the base_classifier is deterministic, fitting with early_stopping and
    # n_iter_no_change=1 should produce equivalent results to fitting without
    # early_stopping
    base_classifier = KNeighborsClassifier()
    threshold = 0.75
    max_iter = 10
    st = SelfTrainingClassifier(base_classifier,
                                max_iter=max_iter,
                                threshold=threshold,
                                n_iter_no_change=1)

    st_no_stop = SelfTrainingClassifier(base_classifier,
                                        max_iter=max_iter,
                                        threshold=threshold,
                                        n_iter_no_change=None)
    st.fit(X_train, y_train_missing_labels)
    st_no_stop.fit(X_train, y_train_missing_labels)
    assert st.n_iter_ < 5
    assert_array_equal(st_no_stop.predict(X_test), st.predict(X_test))
    assert st.termination_condition_ == "early_stopping"
    assert st_no_stop.termination_condition_ == "max_iter" or "all_labeled"


def test_strings_dtype():
    clf = SelfTrainingClassifier(KNeighborsClassifier())
    X, y = make_blobs(n_samples=30, random_state=0,
                      cluster_std=0.1)
    labels_multiclass = ["one", "two", "three"]

    y_strings = np.take(labels_multiclass, y)

    with pytest.raises(ValueError, match="dtype"):
        clf.fit(X, y_strings)


@pytest.mark.parametrize("verbose", [True, False])
def test_verbose(verbose):
    old_stdout = sys.stdout
    sys.stdout = output = StringIO()

    clf = SelfTrainingClassifier(KNeighborsClassifier(), verbose=verbose)
    clf.fit(X_train, y_train_missing_labels)

    sys.stdout = old_stdout
    if verbose:
        assert 'iteration' in output.getvalue()
    else:
        assert 'iteration' not in output.getvalue()
