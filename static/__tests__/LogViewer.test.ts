/**
 * LogViewer unit tests
 * Tests WebSocket message handling and log line processing logic
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

// Mock LogMessage interface for testing
interface LogMessage {
    type: 'initial' | 'update' | 'error';
    lines?: string[];
    total_lines?: number;
    message?: string;
}

// Test helper: Simulates the line processing logic from LogViewer
function processLogLines(
    currentLines: string[],
    newLines: string[],
    maxLines: number
): string[] {
    const result = [...currentLines, ...newLines];
    if (result.length > maxLines) {
        return result.slice(-maxLines);
    }
    return result;
}

// Test helper: Determine log level class
function getLogLevelClass(line: string): string {
    if (line.includes('ERROR') || line.includes('[ERROR]')) {
        return 'log-error';
    }
    if (line.includes('WARNING') || line.includes('[WARNING]')) {
        return 'log-warning';
    }
    if (line.includes('DEBUG') || line.includes('[DEBUG]')) {
        return 'log-debug';
    }
    return '';
}

// Test helper: Parse WebSocket message
function parseLogMessage(data: string): LogMessage | null {
    try {
        return JSON.parse(data) as LogMessage;
    } catch {
        return null;
    }
}

describe('LogViewer', () => {
    describe('Log Line Processing', () => {
        it('should add new lines to existing lines', () => {
            const current = ['line1', 'line2'];
            const newLines = ['line3', 'line4'];
            const result = processLogLines(current, newLines, 1000);

            expect(result).toEqual(['line1', 'line2', 'line3', 'line4']);
        });

        it('should trim lines when exceeding maxLines', () => {
            const current = ['line1', 'line2', 'line3'];
            const newLines = ['line4', 'line5'];
            const result = processLogLines(current, newLines, 4);

            expect(result).toEqual(['line2', 'line3', 'line4', 'line5']);
            expect(result.length).toBe(4);
        });

        it('should handle empty arrays', () => {
            const result = processLogLines([], [], 1000);
            expect(result).toEqual([]);
        });

        it('should not exceed maxLines even with large initial load', () => {
            const current: string[] = [];
            const newLines = Array.from({ length: 2000 }, (_, i) => `line${i}`);
            const result = processLogLines(current, newLines, 1000);

            expect(result.length).toBe(1000);
            expect(result[0]).toBe('line1000');
            expect(result[999]).toBe('line1999');
        });
    });

    describe('Log Level Detection', () => {
        it('should detect ERROR level', () => {
            expect(getLogLevelClass('[ERROR] Something failed')).toBe('log-error');
            expect(getLogLevelClass('2024-01-01 ERROR: Crash')).toBe('log-error');
        });

        it('should detect WARNING level', () => {
            expect(getLogLevelClass('[WARNING] Deprecated API')).toBe('log-warning');
            expect(getLogLevelClass('WARNING: Low memory')).toBe('log-warning');
        });

        it('should detect DEBUG level', () => {
            expect(getLogLevelClass('[DEBUG] Variable x = 5')).toBe('log-debug');
            expect(getLogLevelClass('DEBUG: Entering function')).toBe('log-debug');
        });

        it('should return empty string for INFO and other levels', () => {
            expect(getLogLevelClass('[INFO] Server started')).toBe('');
            expect(getLogLevelClass('Normal log message')).toBe('');
        });
    });

    describe('WebSocket Message Parsing', () => {
        it('should parse valid initial message', () => {
            const data = JSON.stringify({
                type: 'initial',
                lines: ['line1', 'line2'],
                total_lines: 2,
            });
            const result = parseLogMessage(data);

            expect(result).not.toBeNull();
            expect(result?.type).toBe('initial');
            expect(result?.lines).toEqual(['line1', 'line2']);
        });

        it('should parse valid update message', () => {
            const data = JSON.stringify({
                type: 'update',
                lines: ['new line'],
            });
            const result = parseLogMessage(data);

            expect(result).not.toBeNull();
            expect(result?.type).toBe('update');
            expect(result?.lines).toEqual(['new line']);
        });

        it('should parse error message', () => {
            const data = JSON.stringify({
                type: 'error',
                message: 'Connection failed',
            });
            const result = parseLogMessage(data);

            expect(result).not.toBeNull();
            expect(result?.type).toBe('error');
            expect(result?.message).toBe('Connection failed');
        });

        it('should return null for invalid JSON', () => {
            const result = parseLogMessage('not valid json');
            expect(result).toBeNull();
        });

        it('should return null for empty string', () => {
            const result = parseLogMessage('');
            expect(result).toBeNull();
        });
    });

    describe('Message Handling Logic', () => {
        it('should process initial message correctly', () => {
            let lines: string[] = [];
            const message: LogMessage = {
                type: 'initial',
                lines: ['log1', 'log2', 'log3'],
            };

            if (message.type === 'initial' && message.lines) {
                lines = message.lines;
            }

            expect(lines).toEqual(['log1', 'log2', 'log3']);
        });

        it('should append update messages to existing lines', () => {
            let lines = ['existing1', 'existing2'];
            const message: LogMessage = {
                type: 'update',
                lines: ['new1', 'new2'],
            };

            if (message.type === 'update' && message.lines) {
                lines = processLogLines(lines, message.lines, 1000);
            }

            expect(lines).toEqual(['existing1', 'existing2', 'new1', 'new2']);
        });

        it('should handle error messages gracefully', () => {
            let lines: string[] = [];
            const message: LogMessage = {
                type: 'error',
                message: 'Log file not found',
            };

            if (message.type === 'error') {
                lines.push(`[ERROR] ${message.message}`);
            }

            expect(lines).toContain('[ERROR] Log file not found');
        });
    });
});
