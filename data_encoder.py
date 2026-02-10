

from sklearn.base import BaseEstimator, TransformerMixin

class FrequencyEncoder(BaseEstimator, TransformerMixin):
    def __init__(self, column):
        self.column = column

    def fit(self, X, y=None):
        self.freq_map_ = X[self.column].value_counts()
        return self

    def transform(self, X):
        X = X.copy()
        X[self.column] = X[self.column].map(self.freq_map_).fillna(0)
        return X

class FurnishingEncoder(BaseEstimator, TransformerMixin):
    def __init__(self, column):
        self.column = column
        self.map_ = {"Fully-Furnished": 2, "Semi-Furnished": 1, "Unfurnished": 0}
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        X = X.copy()
        X[self.column] = X[self.column].map(self.map_).fillna(0)
        return X[[self.column]]
