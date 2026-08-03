// One .env at the repo root, not per-service. Must be imported before anything that
// reads process.env at load time (e.g. the DB pools) — hence first import in index.js.
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, '../../.env') });
