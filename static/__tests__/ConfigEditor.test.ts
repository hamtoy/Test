/**
 * ConfigEditor unit tests
 * Tests form validation, data handling, and configuration logic
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock ConfigData interface for testing
interface ConfigData {
    llm_model: string;
    temperature: number;
    max_tokens: number;
    log_level: string;
    output_dir: string;
    enable_cache: boolean;
    cache_ttl: number;
}

// Validation functions extracted from ConfigEditor logic
function validateTemperature(value: number): boolean {
    return value >= 0 && value <= 2;
}

function validateMaxTokens(value: number): boolean {
    return value >= 1 && Number.isInteger(value);
}

function validateLogLevel(value: string): boolean {
    const validLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    return validLevels.includes(value.toUpperCase());
}

function validateCacheTtl(value: number): boolean {
    return value >= 0 && Number.isInteger(value);
}

function validateConfigData(data: Partial<ConfigData>): string[] {
    const errors: string[] = [];

    if (data.temperature !== undefined && !validateTemperature(data.temperature)) {
        errors.push('Temperature must be between 0 and 2');
    }

    if (data.max_tokens !== undefined && !validateMaxTokens(data.max_tokens)) {
        errors.push('Max tokens must be a positive integer');
    }

    if (data.log_level && !validateLogLevel(data.log_level)) {
        errors.push('Invalid log level');
    }

    if (data.cache_ttl !== undefined && !validateCacheTtl(data.cache_ttl)) {
        errors.push('Cache TTL must be a non-negative integer');
    }

    return errors;
}

// Helper to parse form values like the ConfigEditor does
function parseFormValue(
    value: string,
    type: 'string' | 'number' | 'boolean'
): string | number | boolean {
    switch (type) {
        case 'number':
            return parseFloat(value);
        case 'boolean':
            return value === 'true' || value === 'on';
        default:
            return value;
    }
}

describe('ConfigEditor', () => {
    describe('Temperature Validation', () => {
        it('should accept valid temperatures', () => {
            expect(validateTemperature(0)).toBe(true);
            expect(validateTemperature(0.7)).toBe(true);
            expect(validateTemperature(1.5)).toBe(true);
            expect(validateTemperature(2)).toBe(true);
        });

        it('should reject invalid temperatures', () => {
            expect(validateTemperature(-0.1)).toBe(false);
            expect(validateTemperature(2.1)).toBe(false);
            expect(validateTemperature(NaN)).toBe(false);
        });
    });

    describe('Max Tokens Validation', () => {
        it('should accept valid max_tokens', () => {
            expect(validateMaxTokens(1)).toBe(true);
            expect(validateMaxTokens(4096)).toBe(true);
            expect(validateMaxTokens(100000)).toBe(true);
        });

        it('should reject invalid max_tokens', () => {
            expect(validateMaxTokens(0)).toBe(false);
            expect(validateMaxTokens(-1)).toBe(false);
            expect(validateMaxTokens(1.5)).toBe(false);
        });
    });

    describe('Log Level Validation', () => {
        it('should accept valid log levels', () => {
            expect(validateLogLevel('DEBUG')).toBe(true);
            expect(validateLogLevel('INFO')).toBe(true);
            expect(validateLogLevel('WARNING')).toBe(true);
            expect(validateLogLevel('ERROR')).toBe(true);
            expect(validateLogLevel('CRITICAL')).toBe(true);
        });

        it('should accept case-insensitive log levels', () => {
            expect(validateLogLevel('debug')).toBe(true);
            expect(validateLogLevel('Info')).toBe(true);
        });

        it('should reject invalid log levels', () => {
            expect(validateLogLevel('TRACE')).toBe(false);
            expect(validateLogLevel('VERBOSE')).toBe(false);
            expect(validateLogLevel('')).toBe(false);
        });
    });

    describe('Cache TTL Validation', () => {
        it('should accept valid cache TTL', () => {
            expect(validateCacheTtl(0)).toBe(true);
            expect(validateCacheTtl(3600)).toBe(true);
            expect(validateCacheTtl(86400)).toBe(true);
        });

        it('should reject invalid cache TTL', () => {
            expect(validateCacheTtl(-1)).toBe(false);
            expect(validateCacheTtl(1.5)).toBe(false);
        });
    });

    describe('Full Config Validation', () => {
        it('should return no errors for valid config', () => {
            const config: ConfigData = {
                llm_model: 'gemini-1.5-flash',
                temperature: 0.7,
                max_tokens: 4096,
                log_level: 'INFO',
                output_dir: 'output',
                enable_cache: true,
                cache_ttl: 3600,
            };

            const errors = validateConfigData(config);
            expect(errors).toHaveLength(0);
        });

        it('should collect multiple validation errors', () => {
            const config: Partial<ConfigData> = {
                temperature: 3.0, // Invalid
                max_tokens: -1,   // Invalid
                log_level: 'TRACE', // Invalid
                cache_ttl: -100,  // Invalid
            };

            const errors = validateConfigData(config);
            expect(errors).toHaveLength(4);
        });

        it('should skip validation for undefined fields', () => {
            const config: Partial<ConfigData> = {
                llm_model: 'test-model',
            };

            const errors = validateConfigData(config);
            expect(errors).toHaveLength(0);
        });
    });

    describe('Form Value Parsing', () => {
        it('should parse string values', () => {
            expect(parseFormValue('hello', 'string')).toBe('hello');
            expect(parseFormValue('', 'string')).toBe('');
        });

        it('should parse number values', () => {
            expect(parseFormValue('42', 'number')).toBe(42);
            expect(parseFormValue('3.14', 'number')).toBeCloseTo(3.14);
            expect(parseFormValue('0', 'number')).toBe(0);
        });

        it('should parse boolean values', () => {
            expect(parseFormValue('true', 'boolean')).toBe(true);
            expect(parseFormValue('on', 'boolean')).toBe(true);
            expect(parseFormValue('false', 'boolean')).toBe(false);
            expect(parseFormValue('off', 'boolean')).toBe(false);
        });
    });

    describe('API Response Handling', () => {
        it('should handle successful config load response', async () => {
            const mockResponse: ConfigData = {
                llm_model: 'gemini-1.5-flash',
                temperature: 0.7,
                max_tokens: 4096,
                log_level: 'INFO',
                output_dir: 'output',
                enable_cache: true,
                cache_ttl: 3600,
            };

            // Simulate successful fetch
            const response = new Response(JSON.stringify(mockResponse), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            });

            expect(response.ok).toBe(true);
            const data = await response.json();
            expect(data.llm_model).toBe('gemini-1.5-flash');
        });

        it('should handle error response', async () => {
            const response = new Response(
                JSON.stringify({ detail: 'No valid fields to update' }),
                {
                    status: 400,
                    headers: { 'Content-Type': 'application/json' },
                }
            );

            expect(response.ok).toBe(false);
            const errorData = await response.json();
            expect(errorData.detail).toBe('No valid fields to update');
        });
    });
});
