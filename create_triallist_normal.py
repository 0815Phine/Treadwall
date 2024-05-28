import numpy as np
import random

# Number of entries
n = 25

# Mean and standard deviation for the normal distribution
mean = n / 3 #results in each value being presented roughly one-third of the time
std_dev = mean / 2  

# Generate normally distributed counts for 'C' = centre, 'R' = right, 'L' = left
counts = np.random.normal(loc=mean, scale=std_dev, size=3).astype(int)

# Ensure the sum is 25 by adjusting the counts
while sum(counts) != n:
    diff = n - sum(counts)
    idx = np.random.choice(3)
    counts[idx] += diff if abs(diff) <= 1 else np.sign(diff)

# Create the list with the generated counts
entries = ['C'] * counts[0] + ['R'] * counts[1] + ['L'] * counts[2]

# Shuffle the list to randomize the order
random.shuffle(entries)

print(entries)