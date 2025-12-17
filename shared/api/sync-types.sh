#!/bin/bash

# 1. Download the latest API definition from the running Engine
echo "Fetching OpenAPI spec from Engine..."
curl http://localhost:8000/openapi.json > shared/api/openapi.json

# 2. Generate TypeScript types for the Frontend
echo "Generating TypeScript types..."
npx openapi-typescript shared/api/openapi.json -o web/src/types/api.d.ts

echo "Done! Frontend types are now in sync with Engine."