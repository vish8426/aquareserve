import type { EChartsOption } from "echarts";
import * as echarts from "echarts";
import { useEffect, useRef } from "react";

// Thin React wrapper around Apache ECharts: Mounts a chart, updates it when the option changes and resizes it with the container. 
// Keeps the dependency surface small (no extra React wrapper library).
export default function Chart({
  option,
  height = 320,
}: {
  option: EChartsOption;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    chart.current = echarts.init(ref.current);
    const onResize = () => chart.current?.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, true);
  }, [option]);

  return <div ref={ref} style={{ width: "100%", height }} />;
}
