// Where the app keeps its settings: secrets come from the environment, never from the code.
module.exports = {
  PORT: Number(process.env.PORT || 3000),
  STORE_URL: process.env.STORE_URL || 'http://localhost',
  STORE_KEY: process.env.STORE_KEY || '',
};
