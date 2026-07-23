"use client"

import { useApi } from '@/hooks/useApi';
import {
  getDailyRevenue,
  getCitySales,
  getStockoutRisks,
  getCustomerDistribution,
  getTopProductPairs,
  getAIDecisions,
} from '@/services/api';

import StatCard from '@/components/dashboard/StatCard';
import RevenueChart from '@/components/dashboard/RevenueChart';
import CitySalesChart from '@/components/dashboard/CitySalesChart';
import StockoutTable from '@/components/dashboard/StockoutTable';
import CustomerChart from '@/components/dashboard/CustomerChart';
import ProductPairsTable from '@/components/dashboard/ProductPairsTable';
import AIDecisionFeed from '@/components/dashboard/AIDecisionFeed';
import { SkeletonCard, SkeletonChart, SkeletonTable } from '@/components/dashboard/LoadingSkeleton';

export default function Home() {
  const { data: revenueData, loading: revenueLoading, error: revenueError } = useApi(getDailyRevenue);
  const { data: citySalesData, loading: citySalesLoading } = useApi(getCitySales);
  const { data: stockoutData, loading: stockoutLoading } = useApi(getStockoutRisks);
  const { data: customerData, loading: customerLoading } = useApi(getCustomerDistribution);
  const { data: productPairsData, loading: productPairsLoading } = useApi(getTopProductPairs);
  const { data: aiDecisionsData, loading: aiDecisionsLoading } = useApi(getAIDecisions);

  // Calculate summary stats from revenue data
  const totalRevenue = revenueData?.reduce((sum, d) => sum + d.revenue, 0) || 0;
  const avgDailyRevenue = revenueData ? totalRevenue / revenueData.length : 0;
  const lastRevenue = revenueData?.[0]?.revenue || 0;
  const prevRevenue = revenueData?.[1]?.revenue || 0;
  const revenueTrend = prevRevenue > 0 ? ((lastRevenue - prevRevenue) / prevRevenue) * 100 : 0;

  // Calculate city stats
  const totalCities = citySalesData?.length || 0;
  const totalStores = citySalesData?.reduce((sum, d) => sum + d.active_stores, 0) || 0;

  // Calculate customer stats
  const totalCustomers = customerData?.reduce((sum, d) => sum + d.customer_count, 0) || 0;

  return (
    <main className="min-h-screen bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">RetailOS Dashboard</h1>
          <p className="text-gray-400">Real-time analytics and AI-driven insights</p>
        </div>

        {/* Error State */}
        {revenueError && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <p className="text-red-400 text-sm">
              ⚠️ Error loading data: {revenueError}
            </p>
          </div>
        )}

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {revenueLoading ? (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          ) : (
            <>
              <StatCard
                title="Total Revenue"
                value={`₹${totalRevenue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
                subtitle={`Last ${revenueData?.length || 0} days`}
                trend={{
                  value: Math.abs(revenueTrend),
                  isPositive: revenueTrend > 0,
                }}
              />
              <StatCard
                title="Avg Daily Revenue"
                value={`₹${avgDailyRevenue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
                subtitle="Per day average"
              />
              <StatCard
                title="Active Cities"
                value={totalCities}
                subtitle={`${totalStores} stores`}
              />
              <StatCard
                title="Total Customers"
                value={totalCustomers.toLocaleString('en-IN')}
                subtitle="Across all cities"
              />
            </>
          )}
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {revenueLoading ? (
            <SkeletonChart />
          ) : (
            <RevenueChart data={revenueData || []} />
          )}

          {citySalesLoading ? (
            <SkeletonChart />
          ) : (
            <CitySalesChart data={citySalesData || []} />
          )}
        </div>

        {/* Customer Distribution */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {customerLoading ? (
            <SkeletonChart />
          ) : (
            <CustomerChart data={customerData || []} />
          )}

          {productPairsLoading ? (
            <SkeletonChart />
          ) : (
            <ProductPairsTable data={productPairsData || []} />
          )}
        </div>

        {/* Inventory Table */}
        <div className="mb-8">
          {stockoutLoading ? (
            <SkeletonTable />
          ) : (
            <StockoutTable data={stockoutData || []} />
          )}
        </div>

        {/* AI Decision Feed */}
        <div className="mb-8">
          {aiDecisionsLoading ? (
            <SkeletonChart />
          ) : (
            <AIDecisionFeed data={aiDecisionsData || []} />
          )}
        </div>
      </div>
    </main>
  );
}
