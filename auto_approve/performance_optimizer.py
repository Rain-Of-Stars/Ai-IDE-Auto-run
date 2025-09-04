# -*- coding: utf-8 -*-
"""
性能优化器 - 针对CPU占用高的问题进行算法优化
主要优化策略：
1. 智能模板缓存和预处理
2. ROI区域自适应优化
3. 帧率自适应控制
4. 多线程模板匹配
5. 内存池管理
"""
from __future__ import annotations
import time
import threading
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import numpy as np
import cv2
from auto_approve.logger_manager import get_logger


@dataclass
class PerformanceStats:
    """性能统计数据"""
    avg_scan_time: float = 0.0
    avg_match_time: float = 0.0
    cpu_usage_estimate: float = 0.0
    memory_usage_mb: float = 0.0
    frames_processed: int = 0
    templates_matched: int = 0
    last_update: float = 0.0


class TemplateCache:
    """智能模板缓存管理器"""
    
    def __init__(self, max_cache_size: int = 20):  # 减少缓存大小
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, Tuple[np.ndarray, Tuple[int, int]]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._logger = get_logger()

        # 内存管理
        self._last_cleanup = 0.0
        self._cleanup_interval = 30.0  # 每30秒清理一次
    
    def get_template(self, template_path: str, grayscale: bool = True) -> Optional[Tuple[np.ndarray, Tuple[int, int]]]:
        """获取预处理的模板，支持缓存"""
        cache_key = f"{template_path}_{grayscale}"

        # 定期清理缓存
        self._periodic_cleanup()

        with self._lock:
            if cache_key in self._cache:
                self._access_times[cache_key] = time.monotonic()
                return self._cache[cache_key]
        
        # 加载并预处理模板
        try:
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                self._logger.warning(f"无法加载模板: {template_path}")
                return None
            
            if grayscale:
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            
            template_size = (template.shape[1], template.shape[0])
            
            with self._lock:
                # 缓存管理：LRU策略
                if len(self._cache) >= self.max_cache_size:
                    self._evict_oldest()
                
                self._cache[cache_key] = (template, template_size)
                self._access_times[cache_key] = time.monotonic()
            
            return template, template_size
            
        except Exception as e:
            self._logger.error(f"模板加载失败 {template_path}: {e}")
            return None
    
    def _evict_oldest(self):
        """移除最久未使用的缓存项"""
        if not self._access_times:
            return
        
        oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        del self._cache[oldest_key]
        del self._access_times[oldest_key]
    
    def _periodic_cleanup(self):
        """定期清理过期缓存"""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now

        with self._lock:
            if len(self._cache) <= self.max_cache_size // 2:
                return

            # 清理超过1小时未访问的缓存
            expired_keys = []
            for key, access_time in self._access_times.items():
                if now - access_time > 3600:  # 1小时
                    expired_keys.append(key)

            for key in expired_keys:
                self._cache.pop(key, None)
                self._access_times.pop(key, None)

            if expired_keys:
                self._logger.info(f"清理了 {len(expired_keys)} 个过期模板缓存")

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()


class AdaptiveROIManager:
    """自适应ROI管理器"""
    
    def __init__(self, initial_roi: Tuple[int, int, int, int] = (0, 0, 0, 0)):
        self.current_roi = initial_roi
        self.hit_history: List[Tuple[int, int, float]] = []  # (x, y, timestamp)
        self.max_history = 20
        self._logger = get_logger()
    
    def update_hit(self, x: int, y: int):
        """更新命中位置历史"""
        now = time.monotonic()
        self.hit_history.append((x, y, now))
        
        # 保持历史记录在合理范围内
        if len(self.hit_history) > self.max_history:
            self.hit_history = self.hit_history[-self.max_history:]
    
    def get_optimized_roi(self, image_shape: Tuple[int, int]) -> Tuple[int, int, int, int]:
        """基于命中历史优化ROI区域"""
        if len(self.hit_history) < 3:
            return self.current_roi
        
        # 分析最近的命中位置
        recent_hits = [hit for hit in self.hit_history if time.monotonic() - hit[2] < 30.0]
        
        if len(recent_hits) < 2:
            return self.current_roi
        
        # 计算命中区域的边界
        xs = [hit[0] for hit in recent_hits]
        ys = [hit[1] for hit in recent_hits]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # 添加边距
        margin = 100
        roi_x = max(0, min_x - margin)
        roi_y = max(0, min_y - margin)
        roi_w = min(image_shape[1] - roi_x, max_x - min_x + 2 * margin)
        roi_h = min(image_shape[0] - roi_y, max_y - min_y + 2 * margin)
        
        optimized_roi = (roi_x, roi_y, roi_w, roi_h)
        
        # 只有在ROI显著缩小时才更新
        current_area = self.current_roi[2] * self.current_roi[3] if self.current_roi[2] > 0 else image_shape[0] * image_shape[1]
        new_area = roi_w * roi_h
        
        if new_area < current_area * 0.7:  # 新ROI面积小于当前70%时才更新
            self.current_roi = optimized_roi
            self._logger.info(f"ROI优化: {optimized_roi}, 面积减少 {(1-new_area/current_area)*100:.1f}%")
        
        return self.current_roi


class PerformanceOptimizer:
    """性能优化器主类"""
    
    def __init__(self, max_workers: int = 2):
        self.template_cache = TemplateCache()
        self.roi_manager = AdaptiveROIManager()
        self.stats = PerformanceStats()
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._logger = get_logger()
        
        # 性能监控 - 减少内存占用
        self._scan_times: List[float] = []
        self._match_times: List[float] = []
        self._last_stats_update = 0.0
        self._max_stats_history = 50  # 限制历史记录数量

        # 性能优化控制
        self._skip_heavy_operations = False
        self._last_performance_check = 0.0
        self._performance_check_interval = 5.0  # 每5秒检查一次性能
    
    def optimize_template_matching(self, image: np.ndarray, template_paths: List[str],
                                 threshold: float, grayscale: bool = True) -> Tuple[float, Tuple[int, int], Tuple[int, int]]:
        """优化的模板匹配算法"""
        start_time = time.monotonic()

        # 性能检查：如果系统负载过高，跳过复杂操作
        self._check_performance()

        # 应用ROI优化（仅在性能允许时）
        if not self._skip_heavy_operations:
            roi = self.roi_manager.get_optimized_roi(image.shape[:2])
            if roi[2] > 0 and roi[3] > 0:
                roi_image = image[roi[1]:roi[1]+roi[3], roi[0]:roi[0]+roi[2]]
                roi_offset = (roi[0], roi[1])
            else:
                roi_image = image
                roi_offset = (0, 0)
        else:
            # 高负载时直接使用原图像
            roi_image = image
            roi_offset = (0, 0)
        
        if grayscale and len(roi_image.shape) == 3:
            roi_image = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)
        
        # 并行模板匹配
        best_score = 0.0
        best_loc = (0, 0)
        best_size = (0, 0)
        
        if len(template_paths) <= 3 or self._skip_heavy_operations:
            # 模板数量少或高负载时使用串行处理，避免线程开销
            for i, template_path in enumerate(template_paths):
                score, loc, size = self._match_single_template(roi_image, template_path, grayscale)
                if score > best_score:
                    best_score = score
                    best_loc = (loc[0] + roi_offset[0], loc[1] + roi_offset[1])
                    best_size = size

                # 更激进的早期退出策略
                if score > 0.85:  # 降低早期退出阈值
                    self._logger.debug(f"早期退出: 模板{i+1}/{len(template_paths)}, 分数={score:.3f}")
                    break

                # 如果已经处理了一半模板且没有好的匹配，考虑跳过剩余的
                if i >= len(template_paths) // 2 and best_score < 0.3:
                    self._logger.debug(f"中途退出: 已处理{i+1}个模板，最佳分数仅{best_score:.3f}")
                    break
        else:
            # 模板数量多且性能允许时使用并行处理
            futures = []
            for template_path in template_paths:
                future = self._executor.submit(self._match_single_template, roi_image, template_path, grayscale)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    score, loc, size = future.result(timeout=1.0)
                    if score > best_score:
                        best_score = score
                        best_loc = (loc[0] + roi_offset[0], loc[1] + roi_offset[1])
                        best_size = size
                except Exception as e:
                    self._logger.warning(f"并行模板匹配异常: {e}")
        
        # 更新性能统计 - 限制内存使用
        match_time = time.monotonic() - start_time
        self._match_times.append(match_time)
        if len(self._match_times) > self._max_stats_history:
            self._match_times = self._match_times[-self._max_stats_history//2:]
        
        # 更新ROI管理器
        if best_score >= threshold:
            self.roi_manager.update_hit(best_loc[0], best_loc[1])
        
        return best_score, best_loc, best_size
    
    def _match_single_template(self, image: np.ndarray, template_path: str, grayscale: bool) -> Tuple[float, Tuple[int, int], Tuple[int, int]]:
        """单个模板匹配（优化版）"""
        template_data = self.template_cache.get_template(template_path, grayscale)
        if template_data is None:
            return 0.0, (0, 0), (0, 0)

        template, template_size = template_data

        # 快速尺寸检查
        if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
            return 0.0, (0, 0), template_size

        # 性能保护：如果模板太大，跳过匹配
        if self._skip_heavy_operations and (template.shape[0] > 100 or template.shape[1] > 100):
            return 0.0, (0, 0), template_size

        try:
            # 使用更快的匹配方法
            if self._skip_heavy_operations:
                # 高负载时使用更快但精度稍低的方法
                result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            else:
                # 正常负载时使用标准方法
                result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)

            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            return float(max_val), max_loc, template_size
        except Exception as e:
            self._logger.warning(f"模板匹配异常 {template_path}: {e}")
            return 0.0, (0, 0), template_size
    
    def get_adaptive_interval(self, base_interval_ms: int, cpu_load_factor: float = 1.0) -> int:
        """获取自适应扫描间隔 - 优化版本"""
        # 基于CPU负载和匹配性能动态调整间隔
        avg_match_time = sum(self._match_times) / len(self._match_times) if self._match_times else 0.05

        # 更激进的性能保护策略
        if avg_match_time > 0.2:  # 匹配时间超过200ms
            adaptive_factor = min(4.0, avg_match_time / 0.05)  # 更大的惩罚因子
        elif avg_match_time > 0.1:  # 匹配时间超过100ms
            adaptive_factor = 2.0
        elif avg_match_time < 0.03:  # 匹配时间小于30ms
            adaptive_factor = 0.7  # 更积极的加速
        else:
            adaptive_factor = 1.0

        adaptive_interval = int(base_interval_ms * adaptive_factor * cpu_load_factor)
        # 调整范围：最小500ms，最大8s，避免过于频繁的扫描
        return max(500, min(8000, adaptive_interval))
    
    def update_performance_stats(self):
        """更新性能统计"""
        now = time.monotonic()
        if now - self._last_stats_update < 5.0:  # 每5秒更新一次
            return
        
        if self._match_times:
            self.stats.avg_match_time = sum(self._match_times) / len(self._match_times)
        
        if self._scan_times:
            self.stats.avg_scan_time = sum(self._scan_times) / len(self._scan_times)
        
        # 估算CPU使用率（基于匹配时间和间隔的比例）
        if self.stats.avg_scan_time > 0:
            self.stats.cpu_usage_estimate = min(100.0, (self.stats.avg_match_time / self.stats.avg_scan_time) * 100)
        
        self.stats.last_update = now
        self._last_stats_update = now
        
        self._logger.info(f"性能统计 - 平均匹配时间: {self.stats.avg_match_time:.3f}s, "
                         f"估算CPU使用: {self.stats.cpu_usage_estimate:.1f}%")
    
    def _check_performance(self):
        """检查系统性能，决定是否跳过重型操作"""
        now = time.monotonic()
        if now - self._last_performance_check < self._performance_check_interval:
            return

        self._last_performance_check = now

        # 检查平均匹配时间
        if self._match_times:
            avg_match_time = sum(self._match_times[-10:]) / min(len(self._match_times), 10)
            # 如果平均匹配时间超过80ms，启用性能保护模式（更严格的阈值）
            self._skip_heavy_operations = avg_match_time > 0.08

            if self._skip_heavy_operations:
                self._logger.warning(f"性能保护模式已启用，平均匹配时间: {avg_match_time:.3f}s")
            elif avg_match_time > 0.05:
                self._logger.info(f"性能监控: 平均匹配时间: {avg_match_time:.3f}s (接近阈值)")

    def cleanup(self):
        """清理资源"""
        self._executor.shutdown(wait=True)
        self.template_cache.clear()
