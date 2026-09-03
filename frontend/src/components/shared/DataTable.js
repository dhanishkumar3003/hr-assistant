// columns: [{ key, header, render? }]. render(row) overrides plain row[key] rendering.
export default function DataTable({ columns, rows, rowKey = "id", emptyMessage = "No data yet." }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="bg-card border border-border rounded-card p-12 text-center text-text-secondary">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50">
            {columns.map((col) => (
              <th
                key={col.key}
                className="text-left font-semibold text-text-secondary px-4 py-4 border-b border-border whitespace-nowrap"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[rowKey]} className="hover:bg-gray-50 transition duration-300">
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-4 border-b border-border text-text-primary">
                  {col.render ? col.render(row) : (row[col.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
