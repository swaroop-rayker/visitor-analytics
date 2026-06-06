"use client";

import type { EChartsOption } from "echarts";
import { useEffect, useRef } from "react";

export function Chart({ option, className = "h-72" }: { option: EChartsOption; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let chart: import("echarts").ECharts | undefined;
    let observer: ResizeObserver | undefined;
    void import("echarts").then((echarts) => {
      if (!ref.current) return;
      chart = echarts.init(ref.current, "dark", { renderer: "canvas" });
      chart.setOption({ backgroundColor: "transparent", ...option });
      observer = new ResizeObserver(() => chart?.resize());
      observer.observe(ref.current);
    });
    return () => {
      observer?.disconnect();
      chart?.dispose();
    };
  }, [option]);
  return <div ref={ref} className={className} role="img" aria-label="Analytics chart" />;
}

