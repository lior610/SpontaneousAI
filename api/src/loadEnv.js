/**
 * Loads environment variables from the single root .env file.
 *
 * The project keeps one .env at the repo root (not per-service). This module must be
 * imported before any module that reads process.env at load time (e.g. the DB pools),
 * so it is the very first import in index.js.
 */
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, '../../.env') });
