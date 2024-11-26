import json
import os
import math
import numpy as np
from typing import Dict, List, Set
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, scrolledtext
from pyvi import ViTokenizer

class SearchEngine:
    def __init__(self, data_directory: str, stopwords_file: str):
        self.data_directory = data_directory
        self.documents = {}
        self.index = defaultdict(dict)
        self.document_vectors = {}
        self.stop_words = self.load_stopwords(stopwords_file)
        
    def load_stopwords(self, filepath: str) -> Set[str]:
        """Load Vietnamese stopwords from file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                # Read lines and remove whitespace
                stopwords = {line.strip() for line in f if line.strip()}
            return stopwords
        except FileNotFoundError:
            print(f"Warning: Stopwords file not found at {filepath}")
            return set()
        
    def preprocess_text(self, text: str) -> List[str]:
        """Tokenize and remove stop words from Vietnamese text."""
        text = ViTokenizer.tokenize(text.lower())
        tokens = text.split()
        tokens = [token for token in tokens 
                 if token.strip() and token not in self.stop_words]
        return tokens

    def build_index(self):
        """Build inverted index and calculate TF-IDF scores."""
        doc_frequencies = defaultdict(int)
        index_data = defaultdict(lambda: defaultdict(dict))
        
        # First pass: collect term frequencies
        for filename in os.listdir(self.data_directory):
            if filename.endswith('.json'):
                with open(os.path.join(self.data_directory, filename), 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                    self.documents[filename] = doc
                    
                    text = f"{doc['title']} {doc['content']}"
                    tokens = self.preprocess_text(text)
                    
                    # Calculate term frequencies for this document
                    term_freq = defaultdict(int)
                    for token in tokens:
                        term_freq[token] += 1
                        
                    # Update document frequencies
                    for token in set(tokens):
                        doc_frequencies[token] += 1
                        
                    # Store raw term frequencies
                    for token, freq in term_freq.items():
                        self.index[token][filename] = freq
                        index_data[filename][token]['tf'] = freq

        # Calculate and store IDF and TF-IDF scores
        num_docs = len(self.documents)
        for term in self.index:
            idf = 1 + math.log10(num_docs / doc_frequencies[term])
            
            for doc_id in self.index[term]:
                raw_tf = self.index[term][doc_id]
                tf = 1 + math.log10(raw_tf) if raw_tf > 0 else 0
                tf_idf = tf * idf
                
                # Store in main index
                self.index[term][doc_id] = tf_idf
                
                # Store in index_data for JSON
                index_data[doc_id][term].update({
                    'tf': tf,
                    'idf': idf,
                    'tf_idf': tf_idf
                })

        # Save index to JSON file
        try:
            with open('index.json', 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving index file: {e}")

        # Create document vectors
        for doc_id in self.documents:
            vector = {}
            for term in self.index:
                if doc_id in self.index[term]:
                    vector[term] = self.index[term][doc_id]
            self.document_vectors[doc_id] = vector

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """Search for documents matching the query."""
        # Preprocess query
        query_tokens = self.preprocess_text(query)
        
        # Create query term frequencies
        query_tf = defaultdict(int)
        for token in query_tokens:
            query_tf[token] += 1
        
        # Calculate query TF-IDF
        query_vector = defaultdict(float)
        num_docs = len(self.documents)
        for token, freq in query_tf.items():
            if token in self.index:
                # Calculate TF (1 + log10(freq))
                tf = 1 + math.log10(freq) if freq > 0 else 0
                # Calculate IDF (1 + log10(N/df))
                df = len(self.index[token])  # number of docs containing the term
                idf = 1 + math.log10(num_docs / df)
                # Store TF-IDF score
                query_vector[token] = tf * idf

        # Calculate cosine similarity scores
        scores = {}
        for doc_id, doc_vector in self.document_vectors.items():
            # Calculate dot product
            dot_product = sum(query_vector[term] * doc_vector.get(term, 0)
                            for term in query_vector)
            
            # Calculate magnitudes
            query_magnitude = math.sqrt(sum(score ** 2 for score in query_vector.values()))
            doc_magnitude = math.sqrt(sum(score ** 2 for score in doc_vector.values()))
            
            # Calculate cosine similarity
            if query_magnitude and doc_magnitude:
                scores[doc_id] = dot_product / (query_magnitude * doc_magnitude)
            else:
                scores[doc_id] = 0

        # Sort documents by score
        ranked_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top K results
        results = []
        for doc_id, score in ranked_docs[:top_k]:
            doc = self.documents[doc_id]
            results.append({
                'title': doc['title'],
                'content': doc['content'],
                'score': f"{score:.4f}",
                'date': doc['date']
            })
        return results

class SearchGUI:
    def __init__(self, search_engine: SearchEngine):
        self.search_engine = search_engine
        
        # Create main window
        self.window = tk.Tk()
        self.window.title("Document Search Engine")
        self.window.geometry("800x600")
        
        # Create search frame
        search_frame = ttk.Frame(self.window, padding="10")
        search_frame.pack(fill=tk.X)
        
        # Create search entry
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=50)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # Create search button
        search_button = ttk.Button(search_frame, text="Search", command=self.perform_search)
        search_button.pack(side=tk.LEFT, padx=5)
        
        # Create results area
        self.results_area = scrolledtext.ScrolledText(self.window, wrap=tk.WORD, width=80, height=30)
        self.results_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def perform_search(self):
        query = self.search_var.get()
        if query.strip():
            results = self.search_engine.search(query)
            self.display_results(results)
        
    def display_results(self, results: List[dict]):
        self.results_area.delete('1.0', tk.END)
        if not results:
            self.results_area.insert(tk.END, "No results found.")
            return
        
        for i, result in enumerate(results, 1):
            self.results_area.insert(tk.END, f"\n{i}. {result['title']}\n")
            self.results_area.insert(tk.END, f"Score: {result['score']}\n")
            self.results_area.insert(tk.END, f"Date: {result['date']}\n")
            self.results_area.insert(tk.END, f"{result['content']}\n")
            self.results_area.insert(tk.END, "-" * 80 + "\n")

    def run(self):
        self.window.mainloop()

def main():
    # Initialize and build search engine with Vietnamese stopwords
    search_engine = SearchEngine(
        data_directory="data",
        stopwords_file="vietnamese-stopwords-dash.txt"
    )
    search_engine.build_index()
    
    # Create and run GUI
    gui = SearchGUI(search_engine)
    gui.run()

def test_search():
    """Test function to demonstrate TF-IDF calculation and search."""
    # Test documents
    test_docs = [
        {
            'id': 'doc1.json',
            'title': '',
            'content': 'a b a a Thủ tướng mong hai bộ trưởng cùng chạy đua marathon để sớm ký FTA với Saudi Arabia',
            'date': '2024-01-01'
        },
        {
            'id': 'doc2.json',
            'title': '',
            'content': 'c d b b b',
            'date': '2024-01-02'
        },
        {
            'id': 'doc3.json',
            'title': '',
            'content': 'b b d d d d d',
            'date': '2024-01-03'
        },
        {
            'id': 'doc4.json',
            'title': '',
            'content': 'a a a a b',
            'date': '2024-01-03'
        }
    ]
    
    # Initialize search engine with empty directory (we'll add docs manually)
    search_engine = SearchEngine("", "vietnamese-stopwords-dash.txt")
    
    # Manually add documents to the engine
    for doc in test_docs:
        search_engine.documents[doc['id']] = doc
    
    # Build index manually
    doc_frequencies = defaultdict(int)
    search_engine.index = defaultdict(dict)
    
    print("Step 1: Document Processing and Term Frequencies")
    print("-" * 50)
    
    # First pass: collect term frequencies
    for doc in test_docs:
        doc_id = doc['id']
        text = f"{doc['title']} {doc['content']}"
        tokens = search_engine.preprocess_text(text)
        
        print(f"\nDocument: {doc_id}")
        print(f"Tokens: {tokens}")
        
        # Calculate term frequencies for this document
        term_freq = defaultdict(int)
        for token in tokens:
            term_freq[token] += 1
            
        # Update document frequencies
        for token in set(tokens):
            doc_frequencies[token] += 1
            
        # Store term frequencies in index
        for token, freq in term_freq.items():
            search_engine.index[token][doc_id] = freq
            print(f"Raw TF for '{token}': {freq}")
    
    print("\nStep 2: Document Frequencies")
    print("-" * 50)
    for term, df in doc_frequencies.items():
        print(f"Term '{term}' appears in {df} documents")
    
    print("\nStep 3: TF-IDF Calculation")
    print("-" * 50)
    
    # Calculate TF-IDF scores
    num_docs = len(test_docs)
    for term in search_engine.index:
        idf = 1 + math.log10(num_docs / doc_frequencies[term])
        print(f"\nTerm: '{term}'")
        print(f"IDF = 1 + log10({num_docs}/{doc_frequencies[term]}) = {idf:.4f}")
        
        for doc_id in search_engine.index[term]:
            raw_tf = search_engine.index[term][doc_id]
            tf = 1 + math.log10(raw_tf) if raw_tf > 0 else 0
            tf_idf = tf * idf
            search_engine.index[term][doc_id] = tf_idf
            print(f"Document {doc_id}:")
            print(f"  Raw tf: {raw_tf}")
            print(f"  Log tf: {tf:.4f}")
            print(f"  TF-IDF: {tf_idf:.4f}")
    
    # Create document vectors
    for doc_id in search_engine.documents:
        vector = {}
        for term in search_engine.index:
            if doc_id in search_engine.index[term]:
                vector[term] = search_engine.index[term][doc_id]
        search_engine.document_vectors[doc_id] = vector
    
    print("\nStep 4: Search Results")
    print("-" * 50)
    test_query = "Thủ tướng mong hai bộ trưởng cùng 'chạy đua marathon' để sớm ký FTA với Saudi Arabia"
    print(f"Query: '{test_query}'")
    results = search_engine.search(test_query)
    
    for i, result in enumerate(results, 1):
        print(f"\nResult {i}:")
        print(f"Title: {result['title']}")
        print(f"Score: {result['score']}")
        print(f"Content: {result['content']}")

if __name__ == "__main__":
    # test_search() # for testing
    main() # for GUI