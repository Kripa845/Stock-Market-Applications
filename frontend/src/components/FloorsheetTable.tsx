import type { FloorsheetTransaction } from "../types";

interface FloorsheetTableProps {
  rows: FloorsheetTransaction[];
  loading: boolean;
}

export default function FloorsheetTable({ rows, loading }: FloorsheetTableProps) {
  if (loading) return <div className="empty-state small">Loading floorsheet…</div>;

  if (!rows || rows.length === 0) {
    return (
      <div className="empty-state small">
        No floorsheet transactions for this company/date. Floorsheet data is only collected for a
        sample of days per the assignment scope.
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Buyer broker</th>
            <th>Seller broker</th>
            <th>Qty</th>
            <th>Rate</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.date}</td>
              <td>{row.buyer_broker}</td>
              <td>{row.seller_broker}</td>
              <td>{Number(row.quantity).toLocaleString()}</td>
              <td>{row.rate}</td>
              <td>{row.amount ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
