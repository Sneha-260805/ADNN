import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

np.random.seed(42)

X_train = np.array([
    [-3.0, -3.0],
    [-2.0, -2.0],
    [-1.0, -1.0],
    [-4.0, -2.0],
    [-2.0, -4.0],
    [1.0, 1.0],
    [2.0, 2.0],
    [3.0, 3.0],
    [4.0, 2.0],
    [2.0, 4.0],
])

y_train = np.array([
    0, 0, 0, 0, 0,
    1, 1, 1, 1, 1
])

X_test = np.array([
    [-5.0, -3.0],
    [-3.0, -5.0],
    [3.0, 5.0],
    [5.0, 3.0],
])

y_test = np.array([0, 0, 1, 1])

clf = LogisticRegression(
    C=1.0,
    solver="liblinear",
    random_state=42
)

clf.fit(X_train, y_train)

pred = clf.predict(X_test)
accuracy = accuracy_score(y_test, pred)

assert np.isclose(accuracy, 1.0), (
    f"Expected accuracy 1.0, got {accuracy}"
)

print("PASS")
print("Observed accuracy:", accuracy)
