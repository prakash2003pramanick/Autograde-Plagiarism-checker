from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def calculate_plagiarism_scores(minhash_dict, assignment_text):
    """
    Calculate plagiarism scores for all documents using MinHash Jaccard similarity
    """
    plagiarism_scores = {}
    filenames = list(assignment_text.keys())
    n = len(filenames)

    for i in range(n):
        fname = filenames[i]
        max_sim = 0.0
        for j in range(n):
            if i == j:
                continue
            other_fname = filenames[j]
            sim = minhash_dict[fname].jaccard(minhash_dict[other_fname])
            if sim > max_sim:
                max_sim = sim
        plagiarism_scores[fname] = max_sim * 100  # convert to percentage

    print("\nPlagiarism scores (maximum similarity in %):")
    for fname, score in plagiarism_scores.items():
        print(f"{fname}: {round(score,2)}%")
        
    return plagiarism_scores

def group_similar_assignments(selected_texts, selected_files, group_threshold):
    """
    Group similar assignments based on cosine similarity
    """
    # Vectorize the texts using TF-IDF
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(selected_texts)
    cos_sim = cosine_similarity(tfidf_matrix)

    groups = []  # list of groups, each group is a list of indices
    visited = set()

    for i in range(len(selected_files)):
        if i in visited:
            continue
        current_group = [i]
        visited.add(i)
        for j in range(i + 1, len(selected_files)):
            if j not in visited and cos_sim[i, j] >= group_threshold:
                current_group.append(j)
                visited.add(j)
        groups.append(current_group)

    print("\nGrading groups (by indices):")
    for idx, group in enumerate(groups):
        group_files = [selected_files[i] for i in group]
        print(f"Group {idx+1}: {group_files}")
        
    return groups