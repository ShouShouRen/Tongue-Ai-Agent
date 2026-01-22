import { useEffect, useState } from "react";
import {
    Radar,
    RadarChart,
    PolarGrid,
    PolarAngleAxis,
    PolarRadiusAxis,
    ResponsiveContainer,
    Tooltip,
} from "recharts";
import { X, Calendar, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";

interface WeeklyReportModalProps {
    isOpen: boolean;
    onClose: () => void;
    userId: string;
}

interface ChartData {
    date: string;
    scores: {
        [key: string]: number; // "氣虛": 5, "血虛": 2, etc.
    };
}

const COLORS = [
    "#e74c3c", // red
    "#3498db", // blue
    "#2ecc71", // green
    "#f1c40f", // yellow
    "#9b59b6", // purple
    "#34495e", // black
    "#e67e22", // orange
];

const WeeklyReportModal = ({
    isOpen,
    onClose,
    userId,
}: WeeklyReportModalProps) => {
    const [data, setData] = useState<ChartData[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // View State
    const [viewMode, setViewMode] = useState<"daily" | "weekly">("daily");
    const [currentIndex, setCurrentIndex] = useState<number>(0); // Index for daily view

    // Advice State
    const [advice, setAdvice] = useState<string | null>(null);
    const [adviceLoading, setAdviceLoading] = useState(false);

    useEffect(() => {
        if (isOpen && userId) {
            fetchWeeklyData();
            // Reset state when opening
            setAdvice(null);
            setViewMode("daily");
        }
    }, [isOpen, userId]);

    const fetchWeeklyData = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(
                `http://localhost:8000/api/reports/weekly?user_id=${userId}`
            );
            if (!response.ok) {
                throw new Error("無法獲取週報數據");
            }
            const rawData: ChartData[] = await response.json();

            if (!Array.isArray(rawData)) {
                setData([]);
                return;
            }

            // Sort by date ascending just in case
            rawData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

            setData(rawData);
            // Set to latest record by default
            if (rawData.length > 0) {
                setCurrentIndex(rawData.length - 1);
            }

        } catch (err: any) {
            console.error(err);
            setError(err.message || "發生錯誤");
        } finally {
            setLoading(false);
        }
    };

    const fetchAdvice = async () => {
        setAdviceLoading(true);
        try {
            const response = await fetch("http://localhost:8000/api/tongue/advice", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ user_id: userId })
            });

            if (!response.ok) {
                throw new Error("無法獲取 AI 建議");
            }

            const result = await response.json();
            setAdvice(result.advice);

        } catch (err: any) {
            console.error("獲取 AI 建議時發生錯誤:", err);
            setAdvice("抱歉，目前無法生成建議，請稍後再試。");
        } finally {
            setAdviceLoading(false);
        }
    };

    // Logic to get chart data based on view mode
    const getRadarData = () => {
        if (data.length === 0) return [];

        let currentScores: { [key: string]: number } = {};

        if (viewMode === "daily") {
            const record = data[currentIndex];
            if (record) {
                currentScores = record.scores;
            }
        } else {
            // Weekly Average
            // Calculate average of the last 7 items (or all if less than 7)
            const recentData = data.slice(-7);

            // Sum up
            const sumScores: { [key: string]: number } = {};
            const counts: { [key: string]: number } = {};

            recentData.forEach(d => {
                Object.entries(d.scores).forEach(([key, value]) => {
                    sumScores[key] = (sumScores[key] || 0) + value;
                    counts[key] = (counts[key] || 0) + 1;
                });
            });

            // Average
            Object.keys(sumScores).forEach(key => {
                currentScores[key] = Math.round((sumScores[key] / counts[key]) * 10) / 10;
            });
        }

        return Object.keys(currentScores).map((dim) => ({
            subject: dim,
            score: currentScores[dim],
            fullMark: 10,
        }));
    };

    const handlePrevDay = () => {
        if (currentIndex > 0) setCurrentIndex(currentIndex - 1);
    };

    const handleNextDay = () => {
        if (currentIndex < data.length - 1) setCurrentIndex(currentIndex + 1);
    };

    const radarData = getRadarData();

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-100 bg-gray-50/50">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-mit-red/10 flex items-center justify-center text-mit-red">
                            <Calendar size={18} />
                        </div>
                        <h3 className="font-semibold text-lg text-gray-800">
                            舌診健康分析
                        </h3>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full hover:bg-gray-200 flex items-center justify-center transition-colors text-gray-500"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 flex-1 overflow-y-auto">
                    {loading ? (
                        <div className="h-[300px] flex items-center justify-center text-gray-400">
                            載入中...
                        </div>
                    ) : error ? (
                        <div className="h-[300px] flex items-center justify-center text-red-400">
                            {error}
                        </div>
                    ) : data.length === 0 ? (
                        <div className="h-[300px] flex flex-col items-center justify-center text-gray-400 gap-2">
                            <p>本週尚無數據</p>
                            <p className="text-xs">請先進行舌診分析</p>
                        </div>
                    ) : (
                        <div className="flex flex-col gap-6">
                            {/* Controls */}
                            <div className="flex justify-center bg-gray-100 p-1 rounded-lg self-center">
                                <button
                                    onClick={() => setViewMode("daily")}
                                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === "daily" ? "bg-white text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}
                                >
                                    單日檢視
                                </button>
                                <button
                                    onClick={() => setViewMode("weekly")}
                                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === "weekly" ? "bg-white text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}
                                >
                                    一週平均
                                </button>
                            </div>

                            {/* Navigation (Daily Only) */}
                            {viewMode === "daily" && (
                                <div className="flex items-center justify-between px-4">
                                    <button
                                        onClick={handlePrevDay}
                                        disabled={currentIndex === 0}
                                        className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
                                    >
                                        <ChevronLeft size={20} />
                                    </button>
                                    <span className="font-medium text-gray-700">
                                        {data[currentIndex]?.date}
                                    </span>
                                    <button
                                        onClick={handleNextDay}
                                        disabled={currentIndex === data.length - 1}
                                        className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
                                    >
                                        <ChevronRight size={20} />
                                    </button>
                                </div>
                            )}

                            {/* Chart */}
                            <div className="w-full h-[300px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarData}>
                                        <PolarGrid stroke="#e5e7eb" />
                                        <PolarAngleAxis
                                            dataKey="subject"
                                            tick={{ fill: '#4b5563', fontSize: 13, fontWeight: 500 }}
                                        />
                                        <PolarRadiusAxis
                                            angle={30}
                                            domain={[0, 10]}
                                            tick={false}
                                            axisLine={false}
                                        />
                                        <Radar
                                            name="健康指數"
                                            dataKey="score"
                                            stroke="#D64545"
                                            fill="#D64545"
                                            fillOpacity={0.4}
                                        />
                                        <Tooltip
                                            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                        />
                                    </RadarChart>
                                </ResponsiveContainer>

                                <div className="text-center text-sm text-gray-500">
                                    {viewMode === "daily" ? (
                                        <p className="text-xs text-gray-400">當日分析結果 (0-10)</p>
                                    ) : (
                                        <p className="text-xs text-gray-400">過去 7 天平均數值 (0-10)</p>
                                    )}
                                </div>
                            </div>

                            {/* AI Advice Section */}
                            <div className="border-t border-gray-100 pt-5">
                                {!advice ? (
                                    <button
                                        onClick={fetchAdvice}
                                        disabled={adviceLoading || data.length === 0}
                                        className="w-full py-3 bg-gradient-to-r from-mit-red to-[#c0392b] text-white rounded-xl shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all flex items-center justify-center gap-2 font-medium disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none"
                                    >
                                        {adviceLoading ? (
                                            <>生成中...</>
                                        ) : (
                                            <>
                                                <Sparkles size={18} />
                                                AI 建議
                                            </>
                                        )}
                                    </button>
                                ) : (
                                    <div className="bg-orange-50 rounded-xl p-4 border border-orange-100">
                                        <div className="flex items-center gap-2 mb-2 text-orange-800 font-semibold">
                                            <Sparkles size={16} />
                                            AI 中醫建議
                                        </div>
                                        <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                                            {advice}
                                        </div>
                                        <button
                                            onClick={() => setAdvice(null)}
                                            className="mt-3 text-xs text-orange-600 hover:text-orange-800 underline"
                                        >
                                            重新生成建議
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-gray-100 bg-gray-50 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-white border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium"
                    >
                        關閉
                    </button>
                </div>
            </div>
        </div>
    );
};

export default WeeklyReportModal;
