"""
Module: clustering.py
Purpose: Cluster complaints to identify root causes using TF-IDF + KMeans.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans


def cluster_texts(texts: list, n_clusters: int = 5) -> list[int]:
    """
    Cluster texts using TF-IDF vectorization and KMeans.

    Args:
        texts: list of complaint strings
        n_clusters: number of clusters (capped to number of samples)

    Returns:
        list of integer cluster labels, one per input text
    """
    if not texts:
        return []

    # Ensure all entries are strings
    texts = ["" if t is None else str(t) for t in texts]

    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(texts)

    # n_clusters must not exceed number of samples
    n_clusters = max(1, min(n_clusters, X.shape[0]))

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    labels = model.fit_predict(X)
    return [int(label) for label in labels]
