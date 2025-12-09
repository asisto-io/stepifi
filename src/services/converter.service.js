// src/services/converter.service.js

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;
const config = require('../config');
const logger = require('../utils/logger');

const FREECAD = '/opt/conda/bin/freecadcmd';

// Required env so FreeCAD runs headless inside Docker
const FREECAD_ENV = {
  ...process.env,
  QT_QPA_PLATFORM: 'offscreen',
  XDG_RUNTIME_DIR: '/tmp/runtime',
  CONDA_PREFIX: '/opt/conda',
  LD_LIBRARY_PATH: '/opt/conda/lib'
};

class ConverterService {
  constructor() {
    this.pythonScript = path.join(config.paths.pythonScripts, 'convert.py');
  }

  /**
   * Check FreeCAD availability
   */
  async checkFreecad() {
    return new Promise((resolve) => {
      const proc = spawn(FREECAD, ['--version'], {
        env: FREECAD_ENV,
        timeout: 8000
      });

      let stdout = '';
      proc.stdout.on('data', (d) => (stdout += d.toString()));

      proc.on('close', (code) => {
        resolve({
          available: code === 0,
          version: stdout.trim()
        });
      });

      proc.on('error', () => resolve({ available: false }));
    });
  }

  /**
   * STL → STEP conversion
   */
  async convert(inputPath, outputPath, options = {}) {
    const tolerance = options.tolerance || config.conversion.defaultTolerance;
    const repair = options.repair !== false;

    try {
      await fs.access(inputPath);
    } catch {
      return { success: false, error: 'Input file not found' };
    }

    return new Promise((resolve) => {
      // FreeCAD requires:
      // freecadcmd convert.py -- <args...>
      const args = [
        this.pythonScript,
        '--',
        inputPath,
        outputPath,
        `--tolerance=${tolerance}`,
        repair ? '--repair' : '--no-repair'
      ];

      logger.info('Running FreeCAD conversion', { cmd: FREECAD, args });

      const proc = spawn(FREECAD, args, {
        env: FREECAD_ENV,
        timeout: config.conversion.timeout
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (d) => (stdout += d.toString()));
      proc.stderr.on('data', (d) => (stderr += d.toString()));

      proc.on('close', (code) => {
        if (code !== 0) {
          return resolve({
            success: false,
            error: stderr.trim() || 'Conversion failed',
            code,
            stderr
          });
        }

        // extract last JSON line
        const lines = stdout.trim().split('\n');
        const last = lines[lines.length - 1];

        try {
          const json = JSON.parse(last);
          resolve(json);
        } catch (err) {
          logger.error('Failed to parse conversion output', { stdout, stderr });
          resolve({
            success: false,
            error: 'Failed to parse conversion result',
            stdout,
            stderr
          });
        }
      });

      proc.on('error', (err) => {
        resolve({
          success: false,
          error: err.message
        });
      });
    });
  }

  /**
   * Mesh info
   */
  async getMeshInfo(inputPath) {
    return new Promise((resolve) => {
      const args = [
        this.pythonScript,
        '--',
        inputPath,
        '/dev/null',
        '--info'
      ];

      const proc = spawn(FREECAD, args, {
        env: FREECAD_ENV,
        timeout: 30000
      });

      let stdout = '';
      proc.stdout.on('data', (d) => (stdout += d.toString()));

      proc.on('close', () => {
        try {
          const lines = stdout.trim().split('\n');
          resolve(JSON.parse(lines.pop()));
        } catch {
          resolve({ success: false, error: 'Failed to parse mesh info' });
        }
      });

      proc.on('error', (err) => {
        resolve({ success: false, error: err.message });
      });
    });
  }
}

module.exports = new ConverterService();
