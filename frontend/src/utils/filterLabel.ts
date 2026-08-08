// Mirrors the backend FilterSpec operator set (see FilterSetBuilder.vue) — kept as
// concise symbols/words for compact filter labels, shared by FilterChainSummary.vue.
const OPERATOR_SYMBOLS: Record<string, string> = {
    '<': '<',
    '<=': '≤',
    '>': '>',
    '>=': '≥',
    contains: 'contains',
    not_contains: 'not contains',
    starts_with: 'starts with',
    ends_with: 'ends with',
    equals: '=',
    not_equals: '≠',
    regex: 'matches',
    is_empty: 'is empty',
    is_not_empty: 'is not empty'
}

export interface FilterLabelParts {
    column: string
    operator: string
    threshold: number | null
    text_value: string | null
}

export function formatFilterLabel(item: FilterLabelParts): string {
    const opLabel = OPERATOR_SYMBOLS[item.operator] ?? item.operator
    if (item.operator === 'is_empty' || item.operator === 'is_not_empty') {
        return `${item.column} ${opLabel}`
    }
    if (item.text_value != null && item.text_value !== '') {
        return `${item.column} ${opLabel} "${item.text_value}"`
    }
    if (item.threshold != null) {
        return `${item.column} ${opLabel} ${item.threshold}`
    }
    return `${item.column} ${opLabel}`
}
