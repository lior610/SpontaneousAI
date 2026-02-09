# Foursquare Attraction Scraper & Enricher

This directory contains the scripts for scraping attraction data from the Foursquare API, processing it, and enriching it with generative AI.

## Execution Flow

The data pipeline consists of several steps:

1.  **Scraping (`main.py`)**: The `main.py` script continuously scrapes attraction data from the Foursquare API for a predefined geographical area (e.g., New York City). It saves the raw, normalized data into `foursquare_ny_attractions.json`. This script is designed to be run continuously.

2.  **Filtering (`filter_places.py`)**: After generating the raw data, `filter_places.py` is run to process it. This script reads `foursquare_ny_attractions.json`, classifies each place as an "attraction" or "utility," and filters out places with unpopular categories. The result is saved to `filtered_places.json`.

3.  **Vibe Enrichment (`get-vibe.py`)**: The `get-vibe.py` script takes the filtered data and uses the Google Gemini API to generate descriptive "vibes," budget estimates, and typical hours for each place. It has special logic to create varied profiles for chain businesses. The final, enriched data is saved as `places_enriched.json`. This script uses caching to avoid re-generating data for places it has already processed.

4.  **Test Data Creation (`create_test_data.py`)**: For development and testing, `create_test_data.py` can be used. It creates a smaller, representative sample of the data from `filtered_places.json` and saves it as `test_places.json`.

## Directory Structure

-   **`src/`**: Contains the Python scripts for the pipeline.
-   **`data/`**: Contains the JSON files that are the inputs and outputs of the pipeline steps.
-   **`cache/`**: Contains cache files to avoid redundant API calls during the enrichment step.

### `data/` Directory

-   **`foursquare_ny_attractions.json`**: Raw attraction data scraped directly from the Foursquare API.
-   **`filtered_places.json`**: The data after being cleaned, filtered, and classified by `filter_places.py`.
-   **`places_enriched.json`**: The final, enriched dataset containing AI-generated descriptions, budget, and hours.
-   **`test_places.json`**: A smaller subset of `filtered_places.json`, used for testing and development.

### `cache/` Directory

-   **`attraction_cache.json`**: Caches the AI-generated data for unique attractions, keyed by their `place_id`. This prevents redundant API calls to the Gemini model.
-   **`chain_cache.json`**: Caches the AI-generated data for chain businesses, keyed by the chain's name. This is especially useful as chains appear multiple times in the data.

## Requirements

The required Python packages for these scripts are listed in `requirements.txt`. They can be installed using pip:

```bash
pip install -r requirements.txt
```
