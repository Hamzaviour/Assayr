/** The numbers behind a chart, for screen readers. */
export function DataTable({ caption, rows }: { caption: string; rows: [string, string][] }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <tbody>
        {rows.map(([key, value], i) => (
          <tr key={`${i}-${key}`}>
            <td>{key}</td>
            <td>{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
