# Logging System Documentation

## Overview

The AI Workforce Orchestrator now includes comprehensive structured logging across all major components. This provides full observability for debugging, monitoring, and compliance requirements.

## Architecture

### Centralized Configuration

Location: `backend/app/core/_logging.py`

The logging system uses a centralized `LoggerConfig` class that:
- Creates rotating file handlers to prevent disk space issues
- Supports different log files for different components
- Configurable via environment variables
- Provides both file and console output

### Log Files

All log files are stored in the `logs/` directory (configurable via `LOG_DIR` environment variable):

| File | Component | Purpose |
|------|-----------|---------|
| `orchestrator.log` | Main application | Startup, shutdown, HTTP requests |
| `agents.log` | Agent operations | All agent executions and decisions |
| `services.log` | Service layer | Business logic operations |
| `api.log` | API routes | Endpoint-specific logging |
| `events.log` | Event queue | Event processing and worker operations |
| `llm.log` | LLM service | AI model calls, fallbacks, errors |

### Log Rotation

- **Max file size**: 10 MB (configurable via `LOG_MAX_BYTES`)
- **Backup count**: 5 files (configurable via `LOG_BACKUP_COUNT`)
- Old logs are automatically rotated to `.log.1`, `.log.2`, etc.

## Configuration

### Environment Variables

Set these in your `.env` file or environment:

```bash
# Logging directory
LOG_DIR=./logs

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Rotation settings
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5

# Custom log format (optional)
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
```

### Log Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| `DEBUG` | Development debugging | Agent decision details, variable values |
| `INFO` | Normal operations | Workflow starts, task assignments, completions |
| `WARNING` | Unexpected but handled | Low confidence scores, fallback activations |
| `ERROR` | Operation failures | API call failures, assignment rejections |
| `CRITICAL` | System failures | Database connection loss, startup failures |

**Production recommendation**: `LOG_LEVEL=INFO`  
**Development recommendation**: `LOG_LEVEL=DEBUG`

## What Gets Logged

### 1. Application Lifecycle

```
=== AI Workforce Orchestrator Starting ===
Database tables created/verified successfully
Application startup complete
```

### 2. HTTP Requests

Every API request is logged with timing:
```
Request: POST /projects
Response: POST /projects - status=200 duration=0.156s
```

### 3. Agent Execution

Each agent run is logged with confidence scores:
```
IntakeAgent completed: confidence=0.85, requires_review=False
PlanningAgent completed: confidence=0.78, tasks_planned=6
StaffingAgent completed: confidence=0.82
```

### 4. Task Assignments

Complete assignment workflow:
```
Assigning task_id=42, difficulty=medium, urgency=high
Found 5 available employees for task_id=42
Best match for task_id=42: employee_id=3, name=Senior Developer, confidence=0.87
Task assignment created: task_id=42 -> employee_id=3, estimated_hours=8, new_load=24
```

### 5. LLM Operations

AI service calls with fallback detection:
```
Initializing LLM service: model=mistralai/Mistral-7B-Instruct-v0.3, temperature=0.2, max_tokens=900, enabled=True
LLM service initialized successfully
Invoking LLM with 2 messages
LLM response received (length=1247 chars)
```

Or when using fallback:
```
LLM service disabled - using fallback mode (no token or LangChain unavailable)
LLM disabled - using fallback project parser
```

### 6. Event Processing

Event queue worker operations:
```
Event worker started: batch_size=10, poll_interval=2.0s
Publishing event: type=task_created, entity=task:42
Event 15 processed successfully
Event worker cycle 5: processed=3, failed=0, total=3
```

### 7. Error Tracking

Full stack traces for debugging:
```
ERROR - Failed to initialize LLM service: Connection timeout
Traceback (most recent call last):
  ...
```

## Usage Examples

### Basic Usage in Code

```python
from app.core._logging import get_logger

logger = get_logger(__name__)

def my_function():
    logger.info("Starting operation")
    try:
        # your code
        logger.debug(f"Processing item: {item_id}")
        result = process_item(item_id)
        logger.info(f"Operation completed successfully: result={result}")
        return result
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        raise
```

### Structured Logging

Log with context for better searchability:

```python
logger.info(
    f"Task assigned: task_id={task.id}, employee_id={employee.id}, "
    f"confidence={confidence:.2f}, estimated_hours={hours}"
)
```

## Monitoring & Analysis

### Viewing Logs

**Real-time monitoring:**
```bash
# All logs
tail -f logs/*.log

# Specific component
tail -f logs/agents.log

# Errors only
tail -f logs/*.log | grep ERROR
```

**Search for patterns:**
```bash
# Find all assignments
grep "Task assignment created" logs/services.log

# Find low confidence warnings
grep "confidence.*below threshold" logs/*.log

# Find LLM fallbacks
grep "fallback" logs/llm.log
```

### Production Monitoring

For production deployments, consider integrating with:
- **Splunk**: Forward logs via file monitoring
- **ELK Stack**: Parse structured log format
- **CloudWatch**: Ship logs to AWS
- **Datadog**: APM + log aggregation

## Troubleshooting

### Problem: No logs appearing

**Check:**
1. Verify `LOG_DIR` directory exists and is writable
2. Check `LOG_LEVEL` - DEBUG shows most detail
3. Ensure logging is imported in the module

### Problem: Log files growing too large

**Solution:**
1. Reduce `LOG_MAX_BYTES` (default 10MB)
2. Reduce `LOG_BACKUP_COUNT` (default 5 files)
3. Increase log level to WARNING or ERROR in production
4. Set up log rotation via system tools (logrotate)

### Problem: Too much noise in logs

**Solution:**
1. Increase `LOG_LEVEL` to WARNING or ERROR
2. Disable DEBUG-level logging in production
3. Filter logs by component (use specific log files)

### Problem: Can't find specific events

**Solution:**
1. Use structured logging with consistent format
2. Include entity IDs in log messages
3. Use grep with multiple patterns:
   ```bash
   grep -E "task_id=42|project_id=15" logs/*.log
   ```

## Best Practices

### DO ✅

- **Log at appropriate levels**: INFO for normal ops, ERROR for failures
- **Include context**: IDs, names, values that help debugging
- **Use structured format**: `key=value` pairs for easy parsing
- **Log entry and exit** of critical operations
- **Log timing** for performance-sensitive operations
- **Use exc_info=True** for exceptions to include stack traces

### DON'T ❌

- **Log sensitive data**: passwords, tokens, API keys
- **Over-log in tight loops**: Can impact performance
- **Use print()**: Always use logger instead
- **Ignore log rotation**: Can fill disk in production
- **Log without context**: "Error occurred" (which error? where?)

## Performance Impact

The logging system is designed to be lightweight:

- **Rotating file handlers** prevent unlimited disk growth
- **Async writes** minimize I/O blocking (built into Python logging)
- **Level filtering** reduces overhead in production
- **Console handler** only shows WARNING+ to reduce terminal noise

**Estimated overhead**: < 1% CPU, < 5ms per request

## Future Enhancements

Planned improvements:
- [ ] JSON-formatted logs for better parsing
- [ ] Log aggregation service integration
- [ ] Metrics extraction from logs
- [ ] Alerting on ERROR/CRITICAL logs
- [ ] Performance profiling integration
- [ ] Distributed tracing support

## Support

For questions or issues with logging:
1. Check log file permissions
2. Verify environment variable configuration
3. Review this documentation
4. Check application startup logs for initialization errors

---

**Last Updated**: 2026-04-06  
**Version**: 2.0
