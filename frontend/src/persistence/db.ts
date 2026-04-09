import { openDB, type DBSchema, type IDBPDatabase } from 'idb'

export interface KvRow {
    key: string
    value: unknown
    updatedAt: number
}

interface BinderdashDB extends DBSchema {
    kv: {
        key: string
        value: KvRow
    }
}

const DB_NAME = 'binderdash-app'
const DB_VERSION = 1

let dbPromise: Promise<IDBPDatabase<BinderdashDB>> | null = null

export function getDb(): Promise<IDBPDatabase<BinderdashDB>> {
    if (!dbPromise) {
        dbPromise = openDB<BinderdashDB>(DB_NAME, DB_VERSION, {
            upgrade(db) {
                if (!db.objectStoreNames.contains('kv')) {
                    db.createObjectStore('kv', { keyPath: 'key' })
                }
            },
        })
    }
    return dbPromise
}
