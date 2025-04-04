import nltk
from datasketch import MinHash

# Download NLTK data
nltk.download('punkt', quiet=True)

def get_shingles(text, default_k=5):
    """
    Create a set of word shingles (n-grams) from the text.
    For short texts (fewer than 50 tokens), use 3-word shingles for better sensitivity.
    """
    tokens = nltk.word_tokenize(text.lower())
    k = 3 if len(tokens) < 50 else default_k
    shingles = set()
    if len(tokens) < k:
        shingles.add(" ".join(tokens))
    else:
        for i in range(len(tokens) - k + 1):
            shingle = ' '.join(tokens[i:i+k])
            shingles.add(shingle)
    return shingles

def compute_min_hash_for_text(text, default_k=5, num_perm=128):
    """
    Compute a MinHash signature for the given text based on its shingles.
    """
    shingles = get_shingles(text, default_k)
    m = MinHash(num_perm=num_perm)
    for shingle in shingles:
        m.update(shingle.encode('utf8'))
    return m