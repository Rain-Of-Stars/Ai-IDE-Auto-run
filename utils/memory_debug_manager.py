# -*- coding: utf-8 -*-
"""
内存调试图像管理器 - 避免磁盘IO的调试图像缓存系统

主要功能：
1. 将调试图像保存在内存中而非磁盘
2. 提供可选的批量导出功能
3. 智能内存管理和清理
4. 调试图像的查看和分析接口
"""
from __future__ import annotations
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from threading import RLock
import numpy as np
import cv2

from auto_approve.logger_manager import get_logger


@dataclass
class DebugImageInfo:
    """调试图像信息"""
    id: str
    name: str
    data: np.ndarray
    timestamp: float
    category: str  # 如 "capture", "roi", "match" 等
    metadata: Dict[str, Any]
    size_bytes: int


class MemoryDebugManager:
    """内存调试图像管理器 - 完全避免磁盘IO的调试系统"""
    
    def __init__(self, max_memory_mb: int = 50, max_images: int = 100):
        self._logger = get_logger()
        self._images: Dict[str, DebugImageInfo] = {}
        self._lock = RLock()
        self._max_memory_mb = max_memory_mb
        self._max_images = max_images
        self._total_memory_usage = 0
        self._enabled = False  # 默认禁用以节省内存
        
    def enable(self, enabled: bool = True):
        """启用或禁用调试图像缓存"""
        self._enabled = enabled
        if not enabled:
            self.clear_all()
        self._logger.info(f"调试图像缓存{'已启用' if enabled else '已禁用'}")
    
    def save_debug_image(self, image: np.ndarray, name: str, category: str = "general", 
                        metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        保存调试图像到内存
        
        Args:
            image: 图像数据
            name: 图像名称
            category: 图像类别
            metadata: 附加元数据
            
        Returns:
            图像ID，如果保存失败返回None
        """
        if not self._enabled or image is None:
            return None
        
        try:
            with self._lock:
                # 检查内存限制
                image_size = image.nbytes
                if self._total_memory_usage + image_size > self._max_memory_mb * 1024 * 1024:
                    self._cleanup_old_images()
                
                # 再次检查
                if self._total_memory_usage + image_size > self._max_memory_mb * 1024 * 1024:
                    self._logger.debug(f"内存不足，跳过保存调试图像: {name}")
                    return None
                
                # 检查图像数量限制
                if len(self._images) >= self._max_images:
                    self._cleanup_old_images()
                
                # 生成唯一ID
                image_id = f"{category}_{name}_{uuid.uuid4().hex[:8]}"
                
                # 创建图像信息
                debug_info = DebugImageInfo(
                    id=image_id,
                    name=name,
                    data=image.copy(),  # 确保数据独立
                    timestamp=time.time(),
                    category=category,
                    metadata=metadata or {},
                    size_bytes=image_size
                )
                
                # 保存到内存
                self._images[image_id] = debug_info
                self._total_memory_usage += image_size
                
                self._logger.debug(f"调试图像已保存到内存: {name} ({image.shape}, {image_size/1024:.1f}KB)")
                return image_id
                
        except Exception as e:
            self._logger.error(f"保存调试图像失败 {name}: {e}")
            return None
    
    def get_debug_image(self, image_id: str) -> Optional[np.ndarray]:
        """获取调试图像数据"""
        with self._lock:
            if image_id in self._images:
                return self._images[image_id].data.copy()
            return None
    
    def list_debug_images(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出调试图像信息"""
        with self._lock:
            images_info = []
            for image_id, debug_info in self._images.items():
                if category is None or debug_info.category == category:
                    images_info.append({
                        'id': image_id,
                        'name': debug_info.name,
                        'category': debug_info.category,
                        'timestamp': debug_info.timestamp,
                        'shape': debug_info.data.shape,
                        'size_bytes': debug_info.size_bytes,
                        'metadata': debug_info.metadata
                    })
            
            # 按时间戳排序（最新的在前）
            images_info.sort(key=lambda x: x['timestamp'], reverse=True)
            return images_info
    
    def export_to_disk(self, output_dir: str, category: Optional[str] = None) -> int:
        """
        将内存中的调试图像导出到磁盘
        
        Args:
            output_dir: 输出目录
            category: 指定类别，None表示导出所有
            
        Returns:
            导出的图像数量
        """
        import os
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            exported_count = 0
            
            with self._lock:
                for image_id, debug_info in self._images.items():
                    if category is None or debug_info.category == category:
                        try:
                            # 生成文件名
                            timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(debug_info.timestamp))
                            filename = f"{timestamp_str}_{debug_info.category}_{debug_info.name}.png"
                            filepath = os.path.join(output_dir, filename)
                            
                            # 保存图像
                            cv2.imwrite(filepath, debug_info.data)
                            exported_count += 1
                            
                        except Exception as e:
                            self._logger.error(f"导出调试图像失败 {image_id}: {e}")
            
            self._logger.info(f"调试图像导出完成: {exported_count}个图像导出到 {output_dir}")
            return exported_count
            
        except Exception as e:
            self._logger.error(f"导出调试图像异常: {e}")
            return 0
    
    def _cleanup_old_images(self):
        """清理旧的调试图像"""
        if not self._images:
            return
        
        # 按时间戳排序，删除最旧的图像
        sorted_images = sorted(
            self._images.items(),
            key=lambda x: x[1].timestamp
        )
        
        # 删除最旧的25%图像，或者超出数量限制的图像
        cleanup_count = max(
            len(sorted_images) // 4,  # 至少删除25%
            len(sorted_images) - self._max_images + 10  # 确保不超过限制
        )
        cleanup_count = max(1, min(cleanup_count, len(sorted_images) - 1))
        
        for i in range(cleanup_count):
            image_id, debug_info = sorted_images[i]
            self._total_memory_usage -= debug_info.size_bytes
            del self._images[image_id]
            self._logger.debug(f"清理旧调试图像: {debug_info.name}")
    
    def clear_category(self, category: str):
        """清空指定类别的调试图像"""
        with self._lock:
            to_remove = []
            for image_id, debug_info in self._images.items():
                if debug_info.category == category:
                    to_remove.append(image_id)
            
            for image_id in to_remove:
                debug_info = self._images[image_id]
                self._total_memory_usage -= debug_info.size_bytes
                del self._images[image_id]
            
            self._logger.info(f"已清空类别 '{category}' 的调试图像: {len(to_remove)}个")
    
    def clear_all(self):
        """清空所有调试图像"""
        with self._lock:
            count = len(self._images)
            self._images.clear()
            self._total_memory_usage = 0
            self._logger.info(f"已清空所有调试图像: {count}个")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存使用统计"""
        with self._lock:
            categories = {}
            for debug_info in self._images.values():
                cat = debug_info.category
                if cat not in categories:
                    categories[cat] = {'count': 0, 'size_bytes': 0}
                categories[cat]['count'] += 1
                categories[cat]['size_bytes'] += debug_info.size_bytes
            
            return {
                'enabled': self._enabled,
                'total_images': len(self._images),
                'total_memory_mb': self._total_memory_usage / (1024 * 1024),
                'max_memory_mb': self._max_memory_mb,
                'max_images': self._max_images,
                'categories': categories
            }
    
    def create_comparison_image(self, image_ids: List[str], title: str = "Comparison") -> Optional[np.ndarray]:
        """
        创建对比图像（将多个调试图像拼接在一起）
        
        Args:
            image_ids: 要对比的图像ID列表
            title: 对比图像标题
            
        Returns:
            拼接后的对比图像
        """
        try:
            with self._lock:
                images = []
                for image_id in image_ids:
                    if image_id in self._images:
                        images.append(self._images[image_id].data)
                
                if not images:
                    return None
                
                # 计算拼接布局
                num_images = len(images)
                cols = int(np.ceil(np.sqrt(num_images)))
                rows = int(np.ceil(num_images / cols))
                
                # 获取最大尺寸
                max_h = max(img.shape[0] for img in images)
                max_w = max(img.shape[1] for img in images)
                
                # 创建拼接画布
                canvas_h = rows * max_h + (rows + 1) * 10  # 添加间距
                canvas_w = cols * max_w + (cols + 1) * 10
                canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
                
                # 拼接图像
                for i, img in enumerate(images):
                    row = i // cols
                    col = i % cols
                    
                    y_start = row * max_h + (row + 1) * 10
                    x_start = col * max_w + (col + 1) * 10
                    
                    h, w = img.shape[:2]
                    canvas[y_start:y_start+h, x_start:x_start+w] = img
                
                # 添加标题
                cv2.putText(canvas, title, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                return canvas
                
        except Exception as e:
            self._logger.error(f"创建对比图像失败: {e}")
            return None


# 全局实例
_debug_manager: Optional[MemoryDebugManager] = None


def get_debug_manager() -> MemoryDebugManager:
    """获取全局调试管理器实例"""
    global _debug_manager
    if _debug_manager is None:
        _debug_manager = MemoryDebugManager()
    return _debug_manager
