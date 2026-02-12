
import json
import random
import os
from collections import Counter

def create_test_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, '..', 'data', 'filtered_places.json')

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            all_places = json.load(f)
    except FileNotFoundError:
        print(f"Error: {input_file} not found. Make sure the path is correct.")
        return

    # 1. Analyze data
    name_counts = Counter(p['name'] for p in all_places if p.get('name'))
    places_by_name = {}
    for p in all_places:
        name = p.get('name')
        if name:
            if name not in places_by_name:
                places_by_name[name] = []
            places_by_name[name].append(p)

    # 2. Categorize
    big_chains = []
    small_chains = []
    unique_places = []

    for name, places_list in places_by_name.items():
        count = len(places_list)
        if count >= 5:
            big_chains.append(name)
        elif 2 <= count <= 4:
            small_chains.append(name)
        else:
            unique_places.extend(places_list)

    attractions = [p for p in unique_places if p.get('type') == 'attraction']
    utilities = [p for p in unique_places if p.get('type') != 'attraction']

    print(f"Found: {len(big_chains)} big chains, {len(small_chains)} small chains, {len(attractions)} unique attractions, {len(utilities)} unique utilities.")

    test_data = []

    # 3. Select data
    # Big Chains
    if len(big_chains) >= 5:
        selected_big_chains = random.sample(big_chains, 5)
        for name in selected_big_chains:
            test_data.extend(places_by_name[name])
        print(f"Selected 5 big chains.")
    else:
        print(f"Warning: Not enough big chains. Found {len(big_chains)}, selected all.")
        for name in big_chains:
            test_data.extend(places_by_name[name])


    # Small Chains
    if len(small_chains) >= 10:
        selected_small_chains = random.sample(small_chains, 10)
        for name in selected_small_chains:
            test_data.extend(places_by_name[name])
        print(f"Selected 10 small chains.")
    else:
        print(f"Warning: Not enough small chains. Found {len(small_chains)}, selected all.")
        for name in small_chains:
            test_data.extend(places_by_name[name])

    # Attractions
    if len(attractions) >= 40:
        test_data.extend(random.sample(attractions, 40))
        print(f"Selected 40 attractions.")
    else:
        print(f"Warning: Not enough attractions. Found {len(attractions)}, selected all.")
        test_data.extend(attractions)


    # Utilities
    if len(utilities) >= 10:
        test_data.extend(random.sample(utilities, 10))
        print(f"Selected 10 utilities.")
    else:
        print(f"Warning: Not enough utilities. Found {len(utilities)}, selected all.")
        test_data.extend(utilities)


    # 4. Write to file
    output_path = os.path.join(script_dir, '..', 'data', 'test_places.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, indent=2, ensure_ascii=False)

    print(f"Successfully created test data file at {output_path} with {len(test_data)} places.")

if __name__ == '__main__':
    create_test_data()
