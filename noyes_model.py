import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

df = pd.read_csv("matches/noyes_actual_matches_arrival_new.csv")

# Convert timestamps to useful numeric features
df["hour"] = pd.to_datetime(df["scheduled_arr"]).dt.hour
df["dayofweek"] = pd.to_datetime(df["scheduled_arr"]).dt.dayofweek
df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)

# One-hot encode direction
df = pd.get_dummies(df, columns=["direction"], drop_first=True)

# Define features and target
features = ["hour", "dayofweek", "is_weekend", "direction_Linden"]  # Howard is baseline
X = df[features]
y = df["error_min"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = LinearRegression()
model.fit(X_train, y_train)

y_pred = model.predict(X_test)

mse = mean_squared_error(y_test, y_pred)
print("Test MSE:", mse)

# Inspect coefficients
coeff_df = pd.DataFrame({
    "feature": X.columns,
    "coefficient": model.coef_
})
print(coeff_df)

import matplotlib.pyplot as plt

plt.scatter(y_test, y_pred, alpha=0.6)
plt.plot([y.min(), y.max()], [y.min(), y.max()], 'k--', lw=2)
plt.xlabel("Actual Delay (min)")
plt.ylabel("Predicted Delay (min)")
plt.title("Predicted vs Actual Arrival Error")
plt.show()