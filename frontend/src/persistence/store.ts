import { getDb } from './db'

/** Strip Vue/Pinia reactive Proxies so IndexedDB structured clone succeeds. */
function toPlainJsonValue(value: unknown): unknown {
    return JSON.parse(JSON.stringify(value)) as unknown
}

export async function kvGet<T>(key: string): Promise<T | undefined> {
    try {
        const db = await getDb()
        const row = await db.get('kv', key)
        return row?.value as T | undefined
    } catch (e) {
        console.warn('IndexedDB kvGet failed', key, e)
        return undefined
    }
}

export async function kvSet(key: string, value: unknown): Promise<void> {
    try {
        const db = await getDb()
        const plain = toPlainJsonValue(value)
        await db.put('kv', { key, value: plain, updatedAt: Date.now() })
    } catch (e) {
        console.warn('IndexedDB kvSet failed', key, e)
    }
}

export async function kvRemove(key: string): Promise<void> {
    try {
        const db = await getDb()
        await db.delete('kv', key)
    } catch (e) {
        console.warn('IndexedDB kvRemove failed', key, e)
    }
}
