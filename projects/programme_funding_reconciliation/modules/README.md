# Project-Specific Modules

Place project-specific transformation logic here that is NOT reusable by other projects.

If a module becomes reusable by 2+ projects, migrate it to `src/core/`.

## Structure

```python
# modules/custom_logic.py
def project_specific_function(df):
    """
    <Description>
    
    Args:
        df: Input DataFrame
    
    Returns:
        Transformed DataFrame
    """
    return df.transform(...)
```
