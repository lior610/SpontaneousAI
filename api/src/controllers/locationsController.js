import authDb from '../db/attractionsConnection.js';

export const getLocations = async (req, res) => {
  try {
    const result = await authDb.query('SELECT id, slug, name, region, country FROM locations ORDER BY name ASC');
    res.json({ locations: result.rows });
  } catch (error) {
    console.error('Error fetching locations:', error);
    res.status(500).json({ error: error.message });
  }
};
