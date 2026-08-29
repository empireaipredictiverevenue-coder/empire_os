
# ── Supabase Backend ─────────────────────────────────────────────────
# Drop-in replacement for SQLiteBackend using sb.py (PostgREST)

class SupabaseBackend:
    """Thin wrapper around sb.py for the funnel, matching SQLiteBackend interface."""
    
    def __init__(self, db_path: str = ":memory:"):
        # db_path ignored - uses SUPABASE_URL/SUPABASE_SERVICE_KEY from env
        from empire_os.sb import _configured
        if not _configured():
            raise RuntimeError("Supabase not configured - set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        self._configured = True
    
    def ensure_schema(self) -> None:
        # Schema managed via SQL migrations, not code
        pass
    
    @property
    def conn(self):
        # Return a mock connection object for compatibility
        class MockConn:
            def execute(self, sql, params=()):
                # Not used for Supabase backend
                return MockCursor()
            def executemany(self, sql, params):
                return MockCursor()
            def executescript(self, sql):
                pass
            def commit(self):
                pass
            def close(self):
                pass
        class MockCursor:
            def fetchone(self):
                return None
            def fetchall(self):
                return []
            @property
            def lastrowid(self):
                return 0
        return MockConn()
    
    def execute(self, sql: str, params: tuple = ()):
        # Parse simple INSERT/SELECT/UPDATE/DELETE and delegate to sb.py
        # This is a simplified implementation - real conversion needed
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("INSERT"):
            return self._execute_insert(sql, params)
        elif sql_upper.startswith("SELECT"):
            return self._execute_select(sql, params)
        elif sql_upper.startswith("UPDATE"):
            return self._execute_update(sql, params)
        elif sql_upper.startswith("DELETE"):
            return self._execute_delete(sql, params)
        else:
            # For schema ops, just return empty cursor
            class MockCursor:
                def fetchone(self): return None
                def fetchall(self): return []
                @property
                def lastrowid(self): return 0
            return MockCursor()
    
    def _execute_insert(self, sql: str, params: tuple):
        # Parse table and columns from INSERT statement
        # This is a simplified parser - would need to be more robust
        import re
        match = re.search(r'INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES', sql, re.IGNORECASE)
        if not match:
            class MockCursor:
                def fetchone(self): return None
                def fetchall(self): return []
                @property
                def lastrowid(self): return 0
            return MockCursor()
        
        table = match.group(1)
        columns = [c.strip() for c in match.group(2).split(',')]
        
        # Build row dict
        row = {}
        for i, col in enumerate(columns):
            if i < len(params):
                row[col] = params[i]
        
        from empire_os.sb import insert
        result = insert(table, row, return_repr=True)
        
        class MockCursor:
            def __init__(self, result):
                self._result = result
            def fetchone(self):
                if self._result and len(self._result) > 0:
                    r = self._result[0]
                    return type('Row', (), r)()
                return None
            def fetchall(self):
                if self._result:
                    return [type('Row', (), r)() for r in self._result]
                return []
            @property
            def lastrowid(self):
                if self._result and len(self._result) > 0:
                    return self._result[0].get('id', 0)
                return 0
        
        return MockCursor(result)
    
    def _execute_select(self, sql: str, params: tuple):
        # Very basic SELECT support - would need full SQL parser for production
        from empire_os.sb import select
        import re
        
        # Try to extract table and basic WHERE
        match = re.search(r'SELECT\s+([^\s]+)\s+FROM\s+(\w+)', sql, re.IGNORECASE)
        if not match:
            class MockCursor:
                def fetchone(self): return None
                def fetchall(self): return []
            return MockCursor()
        
        columns = match.group(1)
        table = match.group(2)
        
        # Extract simple WHERE clauses (col = ?)
        filters = {}
        where_matches = re.findall(r'(\w+)\s*=\s*\?', sql)
        for i, col in enumerate(where_matches):
            if i < len(params):
                filters[col] = params[i]
        
        result = select(table, columns, filters=filters if filters else None, limit=1000)
        
        class MockCursor:
            def __init__(self, rows):
                self._rows = rows
                self._index = 0
            def fetchone(self):
                if self._index < len(self._rows):
                    r = self._rows[self._index]
                    self._index += 1
                    return type('Row', (), r)()
                return None
            def fetchall(self):
                return [type('Row', (), r)() for r in self._rows]
        
        return MockCursor(result)
    
    def _execute_update(self, sql: str, params: tuple):
        from empire_os.sb import update
        import re
        
        match = re.search(r'UPDATE\s+(\w+)\s+SET\s+([^\s]+)', sql, re.IGNORECASE)
        if not match:
            class MockCursor:
                def fetchone(self): return None
                def fetchall(self): return []
            return MockCursor()
        
        table = match.group(1)
        
        # Parse SET columns and WHERE
        # Simplified - just handle the common case
        return MockCursor([])
    
    def _execute_delete(self, sql: str, params: tuple):
        from empire_os.sb import delete
        import re
        
        match = re.search(r'DELETE\s+FROM\s+(\w+)', sql, re.IGNORECASE)
        if not match:
            class MockCursor:
                def fetchone(self): return None
                def fetchall(self): return []
            return MockCursor()
        
        table = match.group(1)
        
        # Parse WHERE
        filters = {}
        where_matches = re.findall(r'(\w+)\s*=\s*\?', sql)
        for i, col in enumerate(where_matches):
            if i < len(params):
                filters[col] = params[i]
        
        delete(table, filters)
        
        class MockCursor:
            def fetchone(self): return None
            def fetchall(self): return []
        
        return MockCursor([])
    
    def executemany(self, sql: str, params: list):
        for p in params:
            self.execute(sql, p)
        class MockCursor:
            def fetchone(self): return None
            def fetchall(self): return []
        return MockCursor()
    
    def executescript(self, sql: str):
        pass
    
    def commit(self):
        pass
    
    def close(self):
        pass

