import Foundation
import SQLite3

struct LibraryError: LocalizedError {
    let errorDescription: String?
    init(_ description: String) { errorDescription = description }
}

private let copySQLText = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

final class Statement {
    private let handle: OpaquePointer
    private let db: OpaquePointer
    init(_ db: OpaquePointer, _ sql: String) throws {
        self.db = db
        var result: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &result, nil) == SQLITE_OK, let result else {
            throw LibraryError(String(cString: sqlite3_errmsg(db)))
        }
        handle = result
    }
    deinit { sqlite3_finalize(handle) }
    func bind(_ values: [SQLValue]) throws {
        sqlite3_reset(handle)
        sqlite3_clear_bindings(handle)
        for (offset, value) in values.enumerated() {
            let index = Int32(offset + 1)
            let result: Int32
            switch value {
            case .text(let text): result = sqlite3_bind_text(handle, index, text, -1, copySQLText)
            case .integer(let number): result = sqlite3_bind_int64(handle, index, number)
            }
            guard result == SQLITE_OK else { throw LibraryError(String(cString: sqlite3_errmsg(db))) }
        }
    }
    @discardableResult func next() throws -> Bool {
        switch sqlite3_step(handle) {
        case SQLITE_ROW: return true
        case SQLITE_DONE: return false
        default: throw LibraryError(String(cString: sqlite3_errmsg(db)))
        }
    }
    func text(_ index: Int32) -> String {
        guard let pointer = sqlite3_column_text(handle, index) else { return "" }
        return String(cString: pointer)
    }
    func integer(_ index: Int32) -> Int64 { sqlite3_column_int64(handle, index) }
}

enum SQLValue { case text(String), integer(Int64) }

final class Database {
    private let handle: OpaquePointer
    init(_ url: URL, readOnly: Bool = false) throws {
        var opened: OpaquePointer?
        let flags = readOnly ? SQLITE_OPEN_READONLY : SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE
        guard sqlite3_open_v2(url.path, &opened, flags | SQLITE_OPEN_FULLMUTEX, nil) == SQLITE_OK, let opened else {
            let reason = opened.map { String(cString: sqlite3_errmsg($0)) } ?? "Cannot open the page index."
            sqlite3_close(opened)
            throw LibraryError(reason)
        }
        handle = opened
        sqlite3_busy_timeout(handle, 3000)
        if !readOnly {
            try execute("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;")
            let version = try statement("PRAGMA user_version")
            guard try version.next(), version.integer(0) <= 1 else { throw LibraryError("This index was created by a newer Page Finder.") }
            if version.integer(0) == 0 { try createSchema() }
        }
    }
    deinit { sqlite3_close_v2(handle) }
    func execute(_ sql: String) throws {
        guard sqlite3_exec(handle, sql, nil, nil, nil) == SQLITE_OK else {
            throw LibraryError(String(cString: sqlite3_errmsg(handle)))
        }
    }
    func statement(_ sql: String) throws -> Statement { try Statement(handle, sql) }
    func transaction(_ action: () throws -> Void) throws {
        try execute("BEGIN IMMEDIATE")
        do { try action(); try execute("COMMIT") }
        catch { try? execute("ROLLBACK"); throw error }
    }
    private func createSchema() throws {
        try transaction {
            try execute("""
                CREATE TABLE IF NOT EXISTS documents(
                    id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE,
                    size INTEGER NOT NULL, modified INTEGER NOT NULL,
                    pages INTEGER NOT NULL DEFAULT 0, extracted INTEGER NOT NULL DEFAULT 0,
                    issue TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS pages(
                    id INTEGER PRIMARY KEY, document INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    number INTEGER NOT NULL, body TEXT NOT NULL, normalized TEXT NOT NULL,
                    UNIQUE(document, number)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS words USING fts5(normalized, content='pages', content_rowid='id', tokenize='trigram');
                CREATE TRIGGER IF NOT EXISTS page_added AFTER INSERT ON pages BEGIN
                    INSERT INTO words(rowid, normalized) VALUES(new.id, new.normalized);
                END;
                CREATE TRIGGER IF NOT EXISTS page_removed AFTER DELETE ON pages BEGIN
                    INSERT INTO words(words, rowid, normalized) VALUES('delete', old.id, old.normalized);
                END;
                PRAGMA user_version=1;
                """)
        }
    }
}
