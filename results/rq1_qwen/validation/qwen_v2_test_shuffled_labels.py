import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

np.random.seed(42)

n_samples = 200
n_features = 20

X = np.random.randn(n_samples, n_features)

y = np.array([0] * 100 + [1] * 100)

shuffled_y = np.random.RandomState(123).permutation(y)

train_idx = np.arange(0, 140)
test_idx = np.arange(140, 200)

X_train = X[train_idx]
X_test = X[test_idx]

y_train = shuffled_y[train_idx]
y_test = shuffled_y[test_idx]

clf = LogisticRegression(
    C=1.0,
    max_iter=1000,
    solver="liblinear",
    random_state=42
)

clf.fit(X_train, y_train)

pred = clf.predict(X_test)
accuracy = accuracy_score(y_test, pred)

chance_level = 0.50

assert abs(accuracy - chance_level) <= 0.20, (
    f"Accuracy {accuracy} is too far from chance."
)

print("PASS")
print("Observed accuracy:", accuracy)
