// API service layer for RetailOS backend

import type {
    DailyRevenue,
    CitySales,
    StockoutRisk,
    CustomerDistribution,
    ProductPair,
    AIDecision,
} from '@/types/kpi';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// NOTE: this ships in the client bundle (NEXT_PUBLIC_*), which is fine for
// demonstrating that the API enforces role-based access, but is NOT how a
// real secret should be handled - a production app would proxy these calls
// through a Next.js server-side route so the key never reaches the browser.
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'demo-analyst-key';

class ApiError extends Error {
    constructor(
        message: string,
        public status?: number,
        public data?: any
    ) {
        super(message);
        this.name = 'ApiError';
    }
}

async function fetchApi<T>(endpoint: string): Promise<T> {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: { 'X-API-Key': API_KEY },
        });

        if (!response.ok) {
            throw new ApiError(
                `API request failed: ${response.statusText}`,
                response.status
            );
        }

        const data = await response.json();
        return data as T;
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }
        throw new ApiError(
            error instanceof Error ? error.message : 'Unknown error occurred'
        );
    }
}

export async function getDailyRevenue(): Promise<DailyRevenue[]> {
    return fetchApi<DailyRevenue[]>('/api/kpi/daily-revenue');
}

export async function getCitySales(): Promise<CitySales[]> {
    return fetchApi<CitySales[]>('/api/kpi/city-sales');
}

export async function getStockoutRisks(): Promise<StockoutRisk[]> {
    return fetchApi<StockoutRisk[]>('/api/kpi/stockout-risks');
}

export async function getCustomerDistribution(): Promise<CustomerDistribution[]> {
    return fetchApi<CustomerDistribution[]>('/api/kpi/customer-distribution');
}

export async function getTopProductPairs(): Promise<ProductPair[]> {
    return fetchApi<ProductPair[]>('/api/kpi/top-product-pairs');
}

export async function getAIDecisions(): Promise<AIDecision[]> {
    return fetchApi<AIDecision[]>('/api/kpi/ai-decisions');
}

export { ApiError };
