// Market basket analysis: products frequently bought together

import type { ProductPair } from '@/types/kpi';

interface ProductPairsTableProps {
    data: ProductPair[];
}

export default function ProductPairsTable({ data }: ProductPairsTableProps) {
    if (!data || data.length === 0) {
        return (
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-lg font-semibold text-white mb-4">Frequently Bought Together</h3>
                <p className="text-gray-500">No product pairs available</p>
            </div>
        );
    }

    return (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Frequently Bought Together</h3>
            <p className="text-gray-500 text-xs mb-4">
                Products purchased by the same customer on the same day. Lift &gt; 1 means the
                pair co-occurs more often than chance.
            </p>

            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="text-gray-400 text-left border-b border-gray-700">
                            <th className="pb-2 pr-4">Product A</th>
                            <th className="pb-2 pr-4">Product B</th>
                            <th className="pb-2 pr-4 text-right">Co-occurrences</th>
                            <th className="pb-2 pr-4 text-right">Confidence</th>
                            <th className="pb-2 text-right">Lift</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.slice(0, 10).map((pair, index) => (
                            <tr key={index} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                                <td className="py-2 pr-4 text-white">{pair.product_a}</td>
                                <td className="py-2 pr-4 text-white">{pair.product_b}</td>
                                <td className="py-2 pr-4 text-right text-gray-300">{pair.co_occurrence_count}</td>
                                <td className="py-2 pr-4 text-right text-gray-300">
                                    {(pair.confidence * 100).toFixed(1)}%
                                </td>
                                <td className="py-2 text-right">
                                    <span className={pair.lift > 1 ? 'text-green-400' : 'text-gray-400'}>
                                        {pair.lift.toFixed(2)}x
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
