/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/*.spec.ts', '**/*.test.ts'],
  testPathIgnorePatterns: ['/node_modules/', '<rootDir>/.stryker-tmp/'],
  coveragePathIgnorePatterns: ['/node_modules/', '<rootDir>/.stryker-tmp/'],
  modulePathIgnorePatterns: ['<rootDir>/.stryker-tmp/'],
  collectCoverage: true,
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov'],
  coverageThreshold: {
    global: {
      branches: 100,
      functions: 100,
      lines: 100,
      statements: 100
    }
  }
};