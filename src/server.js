const express = require('express');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const path = require('path');

const config = require('./config');
const logger = require('./utils/logger');
const redisService = require('./services/redis.service');
const queueService = require('./services/queue.service');
const fileService = require('./services/file.service');
const cleanupService = require('./services/cleanup.service');
const converterService = require('./services/converter.service');
const conversionRoutes = require('./routes/conversion.routes');

const app = express();

app.disable('x-powered-by'); // optional

app.use(cors());
app.use(express.json());
// Static frontend
app.use(express.static(path.join(__dirname, '../public')));

// API routes
app.use('/api', conversionRoutes);

// Health check
app.get('/health', async (req, res) => {
  const redisHealthy = await redisService.healthCheck();
  const freecadCheck = await converterService.checkFreecad();

  res.json({
    status: redisHealthy && freecadCheck.available ? "healthy" : "unhealthy",
    redis: redisHealthy,
    freecad: freecadCheck.available,
    freecadVersion: freecadCheck.version || null,
  });
});

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/index.html'));
});

// Start
async function start() {
  try {
    await fileService.ensureDirectories();
    redisService.connect();

    const queue = queueService.initialize();
    cleanupService.start();

    const fc = await converterService.checkFreecad();
    if (!fc.available) logger.warn("FreeCAD NOT FOUND");

    app.listen(config.port, () => {
      logger.info(`Server running on port ${config.port}`);
    });

  } catch (err) {
    logger.error('Startup failed:', err);
    process.exit(1);
  }
}

start();
