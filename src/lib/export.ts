export type CellValue = string | number

/**
 * Builds a real .xlsx workbook from the given rows and triggers a browser
 * download. Column widths auto-fit to content. No backend required.
 * SheetJS is loaded on demand so it stays out of the initial bundle.
 */
export async function exportRowsToXlsx(opts: {
  filename: string
  sheetName: string
  columns: string[]
  rows: CellValue[][]
}): Promise<void> {
  const XLSX = await import('xlsx')
  const aoa: CellValue[][] = [opts.columns, ...opts.rows]
  const ws = XLSX.utils.aoa_to_sheet(aoa)

  // Auto-size columns based on the longest cell in each column.
  ws['!cols'] = opts.columns.map((header, i) => {
    const longest = Math.max(
      header.length,
      ...opts.rows.map((r) => String(r[i] ?? '').length),
    )
    return { wch: Math.min(Math.max(longest + 2, 10), 60) }
  })

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, opts.sheetName)
  XLSX.writeFile(wb, opts.filename)
}
