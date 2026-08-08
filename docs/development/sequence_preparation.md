# Sequence preparation (development notes)

## Short names: base52 hashes (UID length and hash length)

Prepare Sequences builds short names (≤32 characters by default) in the frontend (`frontend/src/stores/shortName.ts`). Several strategies embed a **fixed-length base52** token from **`hashBase52`**. The **pattern** strategy uses one **set-wide** uid from sorted **prepared DNA** strings; **stem / regex / split** hashes use the row’s **`original_aa`** (pre-tag amino acid sequence), or **`design_id`** if that is empty.

The following describes how those tokens are produced and how **length** (UID length or hash length) affects the output.

### 1. Hash primitive: UTF-8 → FNV-1a 64 → base52

1. **Input string** is encoded as **UTF-8** bytes.
2. **FNV-1a** over 64 bits (offset basis `14695981039346656037`, prime `1099511628211`), XOR/multiply per byte, result **masked to 64 bits**.
3. **`base52(value, L)`** maps the masked integer to exactly **`L`** characters from the alphabet  
   `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz` (52 symbols).  
   It repeatedly takes `value mod 52` as the next digit (least-significant side of the radix expansion), integer-divides by 52, then **reverses** the digit order so the string reads **most significant digit first** for a fixed width **`L`**.

The exported helper is:

```text
hashBase52(input: string, length: number) := base52(fnv1a64(input), length)
```

In code, `base52` clamps **`L`** to **`1 … 32`**. Strategies that expose “hash length” or “UID length” in the UI use **`clampHashLen`**, which further restricts those lengths to **`3 … 10`** for Prepare Sequences short-name use.

So **changing UID / hash length only changes how many base52 characters are emitted**; it does **not** change the hash algorithm. A longer length exposes more of the 64-bit digest in base 52 (more distinguishing power, longer strings). A shorter length truncates to the leading (most significant) base52 digits of the same underlying 64-bit value.

### 2. “Prefix + sorted DNA-set uid + index” (UID length)

For the **pattern** strategy, the middle token (**uid**) is **identical for every row** in the current prepared set. It is the base52 digest of the ** multiset of nucleotide strings** for that set:

1. Take each row’s **`prepared_dna`**, or **`''`** if DNA is not available yet.
2. **Sort** those strings lexicographically (`localeCompare`).
3. Join with record separator **`\x1e`**.
4. **`uid = hashBase52(joined, uidLength)`** with **`uidLength`** clamped to **3–10**.

So the uid changes when **any** row’s prepared DNA changes, when rows are added or removed, or when duplicate counts of identical DNA strings change. It does **not** use amino acid sequence or `design_id` for the uid.

The final short name is **`prefix_uid_index`** (optional prefix, same **uid**, 1-based row index with optional zero padding), then truncated to the global max length.

### 3. Other strategies that hash **only** the original AA (per row)

These use **`hashBase52(original_aa || design_id, hashLen)`** with **`hashLen`** clamped **3–10**:

- **Smart: stem + hash** (when “Include hash” is on)
- **Smart: Regex drop prefix / suffix** (suffix hash after stem)
- **Split + take indices** (when “Add hash” is on)

So for the same sequence and same `hashLen`, two rows with the same `design_id` / `original_aa` would yield the **same** hash segment; deduplication of final short names is handled elsewhere (`uniqueify` in the same module).

### 4. Summary table

| Concept | UI / field | Clamped length | `hashBase52` input |
|--------|------------|----------------|-------------------|
| Pattern uid | UID length | 3–10 | Sorted list of `prepared_dna` (empty if missing), joined with `\x1e` |
| Stem / regex / split hash | Hash length (base52) | 3–10 | `original_aa` or `design_id` if AA missing |

`computeSetFingerprint` remains in `shortName.ts` as an exported helper for other stable-set digests if needed; **pattern** uids do not use it.

Implementation reference: `frontend/src/stores/shortName.ts` (`fnv1a64`, `base52`, `hashBase52`, `computeShortNames`, `rawNameForRow`).
