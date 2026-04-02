const { Client } = require('pg');
const client = new Client({
  connectionString: 'postgresql://postgres:postgres@localhost:5432/stellantis'
});
client.connect()
  .then(() => {
    console.log('Connected successfully to stellantis');
    return client.query('SELECT current_database();');
  })
  .then(res => {
    console.log('Current DB:', res.rows[0]);
    process.exit(0);
  })
  .catch(err => {
    console.error('Connection failed:', err.stack);
    process.exit(1);
  });
