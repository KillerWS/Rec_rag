// BerlinHeatmapModal.js
import { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// 修复Leaflet默认图标问题
import L from 'leaflet';
import { fetchDistrictStats, fetchMapMarkers, selectArea } from '../../api/api';
import { fetchHeatPoints } from '../../api/api';
import ChartBoard from './dataBoard/ChartBoard';
import OverviewPanel from './dataBoard/OverviewPanel';
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

(function() {
  const css = `
    /* 最外层容器保持固定的 hit 区域 */
    .leaflet-marker-icon.custom-number-marker {
      overflow: visible; /* 允许内部放大不被裁剪 */
    }
    /* 内层图标过渡 & 禁止它拦截鼠标 */
    .custom-number-marker .inner-icon {
      transition: transform 0.2s ease;
      pointer-events: none;
      transform-origin: center center;
    }
    /* hover 最外层时，对内层做放大 */
    .leaflet-marker-icon.custom-number-marker:hover .inner-icon {
      transform: scale(1.15);
    }
  `;
  const style = document.createElement('style');
  style.appendChild(document.createTextNode(css));
  document.head.appendChild(style);
})();

// createNumberIcon 修改：多包一层 inner-icon
const createNumberIcon = (number: number, intensity: number = 0.5, size: number = 30, isLargeDistrict: boolean = true) => {
  const baseColor = isLargeDistrict ? 200 : 280;
  const backgroundColor = `hsla(${baseColor - intensity * 60}, 70%, ${50 + intensity * 20}%, 0.8)`;

  return L.divIcon({
    className: 'custom-number-marker',
    html: `
      <div class="inner-icon" style="
        background: ${backgroundColor};
        border: 2px solid white;
        border-radius: 50%;
        width: ${size}px;
        height: ${size}px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: ${Math.max(8, size * 0.35)}px;
        color: white;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.7);
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        position: relative;
      ">
        ${number}
        ${isLargeDistrict
          ? '<div style="position:absolute;top:-3px;right:-3px;width:10px;height:10px;background:#FFD700;border-radius:50%;border:1px solid white;"></div>'
          : ''}
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2]
  });
};

// Typing helpers and relaxed wrappers to avoid react-leaflet prop typing issues at compile time
declare global {
  interface Window {
    confirmDistrictSelection?: (districtName: string, data: any) => void;
  }
}
const AnyMapContainer: any = MapContainer as any;
const AnyTileLayer: any = TileLayer as any;
const AnyGeoJSON: any = GeoJSON as any;
const AnyMarker: any = Marker as any;
const AnyPopup: any = Popup as any;

// 🆕 地图缩放控制组件 - 智能返回上一级
const MapController = ({ selectedDistrict, geojsonData, shouldFitBounds, setBoundsChanged, viewLevel, onLevelChange }: any) => {
  const map = useMap();
  
  // useEffect(() => {
  //   if (selectedDistrict === 'all') {
  //     map.setView([52.5200, 13.4050], viewLevel === 'neighbourhood_group' ? 11 : 13);
  //     if (setBoundsChanged) setBoundsChanged(false);
  //   }
  // }, [selectedDistrict, map, setBoundsChanged, viewLevel]);


  useEffect(() => {
    if (shouldFitBounds && geojsonData && selectedDistrict !== 'all') {
      const selectedFeatures = geojsonData.features.filter(
        (feature: any) => feature.properties.neighbourhood_group === selectedDistrict
      );
      
      if (selectedFeatures.length > 0) {
        const layer = L.geoJSON({
          type: 'FeatureCollection',
          features: selectedFeatures
        });
        const bounds = layer.getBounds();
        
        if (bounds.isValid()) {
          setTimeout(() => {
            map.fitBounds(bounds, { 
              padding: [40, 40],
              maxZoom: 13,
              animate: true,
              duration: 0.5
            });
          }, 100);
          
          if (setBoundsChanged) setBoundsChanged(false);
        }
      }
    }
  }, [shouldFitBounds, geojsonData, selectedDistrict, map, setBoundsChanged]);

  // 🆕 监听地图缩放，自动切换层级
  useEffect(() => {
    const handleZoomEnd = () => {
      const currentZoom = map.getZoom();
      console.log('🔍 地图缩放级别:', currentZoom);
      
      // 当缩放到较小级别时，自动返回上一级
      if (viewLevel === 'neighbourhood' && currentZoom <= 10) {
        console.log('🔙 自动返回大区域视图');
        if (onLevelChange) {
          onLevelChange('neighbourhood_group', null);
        }
      }
    };

    map.on('zoomend', handleZoomEnd);
    
    return () => {
      map.off('zoomend', handleZoomEnd);
    };
  }, [map, viewLevel, onLevelChange]);

  return null;
};

// 🆕 固定 pane 的初始化，确保热力层永远在面图之上且不拦截事件
const PanesSetup = () => {
  const map = useMap();
  useEffect(() => {
    if (!map.getPane('choroplethPane')) {
      const p = map.createPane('choroplethPane');
      p.style.zIndex = '350';
    }
    if (!map.getPane('heatPane')) {
      const p = map.createPane('heatPane');
      p.style.zIndex = '450';
      p.style.pointerEvents = 'none';
    }
    if (!map.getPane('dotsPane')) {
      const p = map.createPane('dotsPane');
      p.style.zIndex = '460';
      p.style.pointerEvents = 'none';
    }
    // markers 默认在 markerPane (zIndex≈600)
  }, [map]);
  return null;
};

// 🆕 修复：悬浮信息提示组件 - 添加自动消失逻辑
const HoverInfoCard = ({ area, position, visible, viewLevel }: any) => {
  const [shouldShow, setShouldShow] = useState(false);
  
  useEffect(() => {
    if (visible && area) {
      setShouldShow(true);
    } else {
      const timer = setTimeout(() => setShouldShow(false), 100);
      return () => clearTimeout(timer);
    }
  }, [visible, area]);
  
  if (!shouldShow || !area) return null;
  
  const isLargeDistrict = viewLevel === 'neighbourhood_group';
  
  return (
    <div 
      style={{
        position: 'fixed',
        left: position?.x + 10,
        top: position?.y + 10,
        background: 'rgba(0,0,0,0.9)',
        color: 'white',
        padding: '8px 12px',
        borderRadius: '6px',
        fontSize: '12px',
        zIndex: 20000,
        pointerEvents: 'none',
        maxWidth: '280px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
      }}
    >
      {/* Header: icon + name */}
      <div style={{ fontWeight: 'bold', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: 6 }}>
        <span>{isLargeDistrict ? '🏛️' : '🏘️'}</span>
        <span style={{ fontSize: 14 }}>{area.name}</span>
      </div>

      {/* Parent hint for neighbourhood level */}
      {!isLargeDistrict && area.parent && (
        <div style={{ margin: '0 0 8px 0', color: '#D1D5DB' }}>
          📍 Located in {area.parent}
        </div>
      )}

      {/* Stats block: mirror marker popup fields */}
      <div style={{ background: 'rgba(255,255,255,0.08)', padding: '10px', borderRadius: 6 }}>
        {Number.isFinite(area.listing_count) && (
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: '#E5E7EB' }}>🏠 Listings:</span>
            <strong style={{ color: '#60A5FA', marginLeft: 6 }}>{Number(area.listing_count).toLocaleString()}</strong>
          </div>
        )}
        {Number.isFinite(area.avg_price) && (
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: '#E5E7EB' }}>💰 Average Price:</span>
            <strong style={{ color: '#34D399', marginLeft: 6 }}>€{area.avg_price}</strong>
          </div>
        )}
        {Number.isFinite(area.total_reviews) && (
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: '#E5E7EB' }}>⭐ Total Reviews:</span>
            <strong style={{ color: '#FBBF24', marginLeft: 6 }}>{Number(area.total_reviews).toLocaleString()}</strong>
          </div>
        )}
        {Number.isFinite(area.popularity_score) && (
          <div>
            <span style={{ color: '#E5E7EB' }}>📊 Popularity:</span>
            <strong style={{ color: '#F472B6', marginLeft: 6 }}>{area.popularity_score}%</strong>
          </div>
        )}
      </div>

      {/* Hint text, mirror marker tone */}
      <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(255,255,255,0.12)', textAlign: 'left', color: '#D1D5DB' }}>
        <small>💡 Hover shows the same stats as the area marker</small>
      </div>
    </div>
  );
};

// 🆕 增强的面包屑导航组件
const BreadcrumbNavigation = ({ viewLevel, parentDistrict, onNavigate }: any) => {
  return (
    <div className="bg-white px-4 py-2 border-b border-gray-200 flex items-center gap-2 text-sm">
      <button
        onClick={() => onNavigate('neighbourhood_group', null)}
        className={`px-3 py-1 rounded transition-colors flex items-center gap-1 ${
          viewLevel === 'neighbourhood_group' 
            ? 'bg-blue-100 text-blue-700 font-medium' 
            : 'text-gray-600 hover:text-blue-600 hover:bg-gray-100'
        }`}
      >
        🏛️ Administrative Districts
      </button>
      
      {parentDistrict && (
        <>
          <span className="text-gray-400">→</span>
          <button
            onClick={() => onNavigate('neighbourhood', parentDistrict)}
            className="px-3 py-1 rounded bg-purple-100 text-purple-700 font-medium flex items-center gap-1"
          >
            🏘️ {parentDistrict} Neighbourhoods
          </button>
          <button
            onClick={() => onNavigate('neighbourhood_group', null)}
            className="ml-2 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors"
          >
            ← Back
          </button>
        </>
      )}
      
      <div className="ml-auto text-xs text-gray-500">
        {viewLevel === 'neighbourhood_group' ? '12 districts' : `${parentDistrict} areas`}
      </div>
    </div>
  );
};

// 🆕 悬浮返回按钮组件
const FloatingBackButton = ({ viewLevel, onNavigate }: any) => {
  if (viewLevel === 'neighbourhood_group') return null;

  return (
    <div className="absolute top-4 right-4 z-[1000]">
      <button
        onClick={() => onNavigate('neighbourhood_group', null)}
        className="bg-white hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-lg shadow-lg border border-gray-200 transition-all duration-200 flex items-center gap-2 hover:shadow-xl"
        title="Return to districts view"
      >
        <span className="text-lg">←</span>
        <span className="font-medium">Back to Districts</span>
      </button>
    </div>
  );
};

// 🔧 修改：增强的区域数字标记组件 - 修复悬浮和点击问题
const DistrictMarkers = ({ markersData, onMarkerClick, onMarkerHover, showMarkers, viewLevel = 'neighbourhood_group', onConfirmSelection, onNavigate }: any) => {
  if (!showMarkers || !markersData || markersData.length === 0) return null;
  const isLargeDistrict = viewLevel === 'neighbourhood_group';
  return (
    <>
      {markersData.map((marker: any) => {
        const baseSize = isLargeDistrict ? 45 : 30;
        const sizeMultiplier = Math.min(1.5, Math.max(0.6, marker.display_number / 1000));
        const markerSize = Math.round(baseSize * sizeMultiplier);
        return (
          <AnyMarker
            key={`${viewLevel}-${marker.district}`}
            position={[marker.position.lat, marker.position.lng]}
            icon={createNumberIcon(marker.display_number, marker.marker_style.color_intensity, markerSize, isLargeDistrict)}
            zIndexOffset={marker.marker_style.z_index}
            
            eventHandlers={{
              mouseover: (e: any) => onMarkerHover && onMarkerHover(marker, e, 'hover'),
              mouseout:  (e: any) => onMarkerHover && onMarkerHover(marker, e, 'leave'),
              click:     (e: any) => {
                e.originalEvent.stopPropagation();
                onMarkerHover && onMarkerHover(null, e, 'leave');
                onMarkerClick(marker.district, marker, isLargeDistrict);
                // ← 手动把 popup 打开
                e.target.openPopup();
              }
            }}
          >
            
            {/* Popup 内容保持不变 */}
            <AnyPopup maxWidth={350} minWidth={300}>
                          <div style={{ minWidth: '280px', fontFamily: 'Arial, sans-serif' }}>
                            <h4 style={{ margin: '0 0 8px 0', color: '#2c3e50', fontSize: '16px' }}>
                              {isLargeDistrict ? '🏛️' : '🏘️'} {marker.district}
                            </h4>
                            
                            {/* 🆕 显示层级信息 */}
                            {marker.parent_district && (
                              <p style={{ margin: '0 0 8px 0', color: '#7f8c8d', fontSize: '12px' }}>
                                📍 Located in {marker.parent_district}
                              </p>
                            )}
                            
                            <div style={{ background: '#f8f9fa', padding: '12px', borderRadius: '8px' }}>
                              <div style={{ marginBottom: '8px', fontSize: '14px' }}>
                                <span style={{ color: '#495057' }}>🏠 Listings:</span> 
                                <strong style={{ color: '#007bff' }}>{marker.popup_info.listing_count.toLocaleString()}</strong>
                              </div>
                              
                              <div style={{ marginBottom: '4px', fontSize: '14px' }}>
                                <span style={{ color: '#495057' }}>💰 Average Price:</span> 
                                <strong style={{ color: '#28a745' }}>€{marker.popup_info.avg_price}</strong>
                              </div>
                              
                              <div style={{ marginBottom: '4px', fontSize: '14px' }}>
                                <span style={{ color: '#495057' }}>⭐ Total Reviews:</span> 
                                <strong style={{ color: '#ffc107' }}>{marker.popup_info.total_reviews.toLocaleString()}</strong>
                              </div>
                              
                              <div style={{ marginBottom: '4px', fontSize: '14px' }}>
                                <span style={{ color: '#495057' }}>📊 Popularity:</span> 
                                <strong style={{ color: '#e83e8c' }}>{marker.popup_info.popularity_percentage}%</strong>
                              </div>
                              
                              {/* 🆕 大区域特有信息 */}
                              {isLargeDistrict && marker.neighbourhood_count && (
                                <div style={{ marginBottom: '4px', fontSize: '14px' }}>
                                  <span style={{ color: '#495057' }}>🏘️ Neighbourhoods:</span> 
                                  <strong style={{ color: '#17a2b8' }}>{marker.neighbourhood_count}</strong>
                                </div>
                              )}
                            </div>
                            
                            {/* 🆕 添加确认选择按钮 */}
                            <div style={{ 
                              marginTop: '12px', 
                              display: 'flex', 
                              gap: '8px',
                              justifyContent: 'space-between'
                            }}>
                              {isLargeDistrict ? (
                                <>
                                  <button
                                    onClick={() => {
                                      console.log('🔍 Popup中的Explore按钮被点击:', marker.district);
                                      // onMarkerClick(marker.district, marker, isLargeDistrict);
                                      onNavigate('neighbourhood', marker.district);
                                    }}
                                    style={{
                                      flex: 1,
                                      padding: '8px 12px',
                                      backgroundColor: '#007bff',
                                      color: 'white',
                                      border: 'none',
                                      borderRadius: '4px',
                                      fontSize: '12px',
                                      cursor: 'pointer',
                                      fontWeight: 'bold'
                                    }}
                                    onMouseOver={(e) => (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#0056b3'}
                                    onMouseOut={(e) => (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#007bff'}
                                  >
                                    🔍 Explore Areas
                                  </button>
                                                                     <button
                                    onClick={async (e) => {
                                      const btn = e.currentTarget as HTMLButtonElement;
                                      btn.disabled = true;
                                      btn.textContent = '⏳ Selecting...';
                                      try {
                                        await onConfirmSelection?.(marker.district, {
                                          level: 'neighbourhood_group',
                                          stats: marker.popup_info
                                        });
                                      } finally {
                                        // 交互逻辑：不恢复按钮，避免重复点击
                                      }
                                    }}
                                    style={{
                                      flex: 1,
                                      padding: '8px 12px',
                                      backgroundColor: '#28a745',
                                      color: 'white',
                                      border: 'none',
                                      borderRadius: '4px',
                                      fontSize: '12px',
                                      cursor: 'pointer',
                                      fontWeight: 'bold'
                                    }}
                                  >
                                    ✅ Select District
                                  </button>
                                </>
                              ) : (
                                <button
                                  onClick={async (e) => {
                                    const btn = e.currentTarget as HTMLButtonElement;
                                    btn.disabled = true;
                                    btn.textContent = '⏳ Selecting...';
                                    try {
                                      await onConfirmSelection?.(marker.district, {
                                        level: 'neighbourhood',
                                        parent: marker.parent_district,
                                        stats: marker.popup_info
                                      });
                                    } finally {
                                      // 交互逻辑：不恢复按钮，避免重复点击
                                    }
                                  }}
                                  style={{
                                    width: '100%',
                                    padding: '8px 12px',
                                    backgroundColor: '#28a745',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    fontSize: '12px',
                                    cursor: 'pointer',
                                    fontWeight: 'bold'
                                  }}
                                >
                                  ✅ Select {marker.district}
                                </button>
                              )}
                            </div>
                            
                            <div style={{ 
                              marginTop: '8px', 
                              padding: '6px', 
                              backgroundColor: isLargeDistrict ? '#e7f3ff' : '#f0e7ff', 
                              borderRadius: '4px',
                              textAlign: 'center',
                              fontSize: '11px'
                            }}>
                              {isLargeDistrict ? (
                                <span style={{ color: '#0056b3' }}>
                                  💡 Choose "Explore" to see neighbourhoods or "Select" for district-wide search
                                </span>
                              ) : (
                                <span style={{ color: '#6a0080' }}>
                                  💡 Click "Select" to filter listings in this specific neighbourhood
                                </span>
                              )}
                            </div>
                          </div>
                          
            </AnyPopup>

          </AnyMarker>
        );
      })}
    </>
  );
};

// 🔥 基于 markersData 的渐变热力层（leaflet.heat）
const MarkersHeatLayer = ({
  enabled,
  markersData,
  mode = 'count',
  radius = 52,
  blur = 34,
  maxZoom = 17
}: any) => {
  const map = useMap();
  const layerRef = useRef<any | null>(null);

  const getWeight = (m: any) => {
    const info = m?.popup_info || {};
    if (mode === 'price') return Number(info.avg_price) || 0;
    if (mode === 'popularity') return Number(info.popularity_percentage) || 0;
    return Number(info.listing_count) || 0;
  };

  useEffect(() => {
    if (!map) return;

    let cancelled = false;

    const run = async () => {
      if (!(L as any).heatLayer) {
        try { await import('leaflet.heat'); } catch (e) {
          console.warn('leaflet.heat failed to load', e);
          return;
        }
      }

      if (layerRef.current) {
        try { map.removeLayer(layerRef.current); } catch {}
        layerRef.current = null;
      }
      if (!enabled || !Array.isArray(markersData) || markersData.length === 0) return;

      const vals = markersData.map(getWeight).filter((v: any) => Number.isFinite(v)) as number[];
      if (vals.length === 0) return;

      vals.sort((a, b) => a - b);
      const pick = (q: number) => vals[Math.floor((vals.length - 1) * q)];
      const lo = pick(0.10);
      const hi = Math.max(pick(0.90), lo + 1e-9);
      const gamma = 0.65;

      const norm = (v: number) => {
        const t = (v - lo) / (hi - lo);
        const clamped = Math.max(0, Math.min(1, t));
        return Math.pow(clamped, gamma);
      };

      const points = (markersData as any[])
        .map((m: any) => {
          const lat = m?.position?.lat;
          const lng = m?.position?.lng;
          if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
          return [lat, lng, norm(getWeight(m))];
        })
        .filter(Boolean) as [number, number, number][];

      console.debug('🌈 heat points:', points.length);
      if (cancelled || points.length === 0) return;

      const heat = (L as any).heatLayer(points, {
        pane: 'heatPane',
        radius,
        blur,
        maxZoom,
        minOpacity: 0.28,
        max: 1.0,
        gradient: {
          0.0: '#7f1d1d',
          0.25: '#b91c1c',
          0.5: '#ef4444',
          0.75: '#f97316',
          1.0: '#fde68a'
        }
      });

      heat.addTo(map);
      layerRef.current = heat;
    };

    run();

    return () => {
      cancelled = true;
      if (layerRef.current) {
        try { map.removeLayer(layerRef.current); } catch {}
        layerRef.current = null;
      }
    };
  }, [map, enabled, markersData, mode, radius, blur, maxZoom]);

  return null;
};

// 🔥 基于后端原始点的热力层（leaflet.heat）
const ServerHeatLayer = ({ enabled, points, radius = 52, blur = 34, maxZoom = 17 }: any) => {
  const map = useMap();
  const layerRef = useRef<any | null>(null);
  useEffect(() => {
    if (!map) return;
    let cancelled = false;
    const run = async () => {
      if (!(L as any).heatLayer) {
        try { await import('leaflet.heat'); } catch (e) {
          console.warn('leaflet.heat failed to load', e);
          return;
        }
      }
      if (layerRef.current) {
        try { map.removeLayer(layerRef.current); } catch {}
        layerRef.current = null;
      }
      if (!enabled || !Array.isArray(points) || points.length === 0) return;
      // 预期 points: [{lat,lng,weight?}]
      const normalized = points
        .map((p: any) => {
          if (Array.isArray(p)) {
            const lat = Number(p[0]);
            const lng = Number(p[1]);
            const w = p.length > 2 ? Number(p[2]) : 1;
            if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
            return [lat, lng, isNaN(w) ? 1 : Math.max(0.01, Math.min(1, w))];
          } else {
            const lat = Number(p.lat), lng = Number(p.lng);
            if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
            const w = p.weight == null ? 1 : Number(p.weight);
            return [lat, lng, isNaN(w) ? 1 : Math.max(0.01, Math.min(1, w))];
          }
        })
        .filter(Boolean) as [number, number, number][];
      if (cancelled || normalized.length === 0) return;
      const heat = (L as any).heatLayer(normalized, {
        pane: 'heatPane',
        radius,
        blur,
        maxZoom,
        minOpacity: 0.28,
        max: 1.0,
        gradient: {
          0.0: '#7f1d1d',
          0.25: '#b91c1c',
          0.5: '#ef4444',
          0.75: '#f97316',
          1.0: '#fde68a'
        }
      });
      heat.addTo(map);
      layerRef.current = heat;
    };
    run();
    return () => {
      cancelled = true;
      if (layerRef.current) {
        try { map.removeLayer(layerRef.current); } catch {}
        layerRef.current = null;
      }
    };
  }, [map, enabled, JSON.stringify(points), radius, blur, maxZoom]);
  return null;
};

// 🔧 修复：NeighbourhoodLayer 组件 - 修复热力图更新问题
const NeighbourhoodLayer = ({ 
  geojsonData, 
  selectedDistrict, 
  districtsData, 
  heatmapMode, 
  onDistrictClick,
  heatmapEnabled,
  enableAutoZoom = true,
  getDistrictBorderColor,
  onConfirmSelection, // 🆕 新增确认选择回调
  viewLevel,
  setHoverInfo,
  onGeometryEnter,
  onGeometryLeave,
  shouldHoldHighlight,
  markersData,
  pointHeatEnabled
}: any) => {
  
  const getDistrictStats = () => {
    if (!districtsData || !Array.isArray(districtsData)) return {} as Record<string, any>;
    
    const toNum = (v: any) => (v == null || v === '' ? 0 : (typeof v === 'number' ? v : Number(v)));
    const stats: Record<string, any> = {};
    districtsData.forEach((district: any) => {
      stats[district.name] = {
        count: toNum(district.listing_count),
        avgPrice: toNum(district.avg_price),
        minPrice: toNum(district.min_price),
        maxPrice: toNum(district.max_price),
        totalReviews: toNum(district.total_reviews),
        popularity: toNum(district.popularity_score),
        heatIntensity: district.heat_intensity
      };
    });
    
    return stats;
  };

  // 🔧 修复：热力图颜色函数 - 移除重复日志
  const getHeatmapColor = (district: string, stats: Record<string, any>) => {
    if (!heatmapEnabled || !stats[district]) {
      return '#f8f9fa';
    }

    const districtStats = stats[district];
    const intensity = districtStats.heatIntensity;

    switch (heatmapMode) {
      case 'count':
        return `hsl(200, 60%, ${85 - intensity.count * 25}%)`;
      case 'price':
        return `hsl(0, 60%, ${85 - intensity.price * 25}%)`;
      case 'popularity':
        return `hsl(120, 60%, ${85 - intensity.popularity * 25}%)`;
      default:
        return '#f8f9fa';
    }
  };

  const getNeighbourhoodStyle = (feature: any) => {
    const group = feature.properties.neighbourhood_group;
    const isSelected = selectedDistrict === group && selectedDistrict !== 'all';
    const stats = getDistrictStats();
    const colorKey = viewLevel === 'neighbourhood' ? feature.properties.neighbourhood : group;
    const borderColor = getDistrictBorderColor(group);
    
    return {
      fillColor: getHeatmapColor(colorKey, stats),
      weight: isSelected ? 2.5 : 1.0,
      opacity: 1,
      color: isSelected ? '#FFD700' : borderColor,
      dashArray: isSelected ? '' : '',
      fillOpacity: isSelected ? 0.5 : (pointHeatEnabled ? 0.12 : 0.35)
    } as any;
  };

  // 管理当前高亮的图层 & 延迟取消的定时器
  const hoverRef = useRef<{ layer: any | null; timer: ReturnType<typeof setTimeout> | null }>({
    layer: null,
    timer: null
  });

  // 用 marker 构造查找表（按名称匹配）
  const markerMap = useRef<Record<string, any>>({});
  const normalizeKey = (s: string) => (s || '').toString().toLowerCase().replace(/[^a-z0-9]/g, '');
  useEffect(() => {
    const map: Record<string, any> = {};
    (markersData || []).forEach((m: any) => {
      map[normalizeKey(m.district)] = m;
    });
    markerMap.current = map;
  }, [markersData]);

  const getAreaFromMarker = (name: string, parentHint?: string) => {
    const m = markerMap.current[normalizeKey(name)];
    if (!m) return null;
    return {
      name: m.district,
      listing_count: m.popup_info?.listing_count,
      avg_price: m.popup_info?.avg_price,
      total_reviews: m.popup_info?.total_reviews,
      popularity_score: m.popup_info?.popularity_percentage,
      parent: m.parent_district ?? parentHint
    };
  };

  const cancelUnhighlight = () => {
    if (hoverRef.current.timer) {
      clearTimeout(hoverRef.current.timer);
      hoverRef.current.timer = null;
    }
  };

  const highlightLayer = (lyr: any) => {
    try {
      lyr.setStyle({ weight: 3, color: '#FFD700', dashArray: '', fillOpacity: 0.6 });
      if (lyr.bringToFront) lyr.bringToFront();
    } catch {}
  };

  const resetLayerStyle = (lyr: any, feature: any) => {
    try { lyr.setStyle(getNeighbourhoodStyle(feature)); } catch {}
  };

  const scheduleUnhighlight = (lyr: any, feature: any, onLeave?: () => void) => {
    cancelUnhighlight();

    const tryUnhighlight = () => {
      // 仍在图形/标记/弹窗/悬浮卡片之一上？继续等
      if (typeof shouldHoldHighlight === 'function' && shouldHoldHighlight()) {
        hoverRef.current.timer = setTimeout(tryUnhighlight, 120);
        return;
      }
      if (hoverRef.current.layer === lyr) {
        resetLayerStyle(lyr, feature);
        hoverRef.current.layer = null;
      }
      if (onLeave) onLeave();
    };

    // 初次等待 180ms，然后按需轮询
    hoverRef.current.timer = setTimeout(tryUnhighlight, 180);
  };

  useEffect(() => {
    return () => {
      cancelUnhighlight();
      hoverRef.current.layer = null;
    };
  }, []);

  // 名称归一化与稳健匹配，避免 GeoJSON 与 API 返回的命名差异导致查不到数据
  const getStatsForName = (rawName: string) => {
    const stats = getDistrictStats();
    if (stats[rawName]) return stats[rawName];
    const normalizedMap: Record<string, any> = {};
    Object.keys(stats).forEach((k) => { normalizedMap[normalizeKey(k)] = (stats as any)[k]; });
    return normalizedMap[normalizeKey(rawName)] || {};
  };

  const onEachFeature = (feature: any, layer: any) => {
    // 取名用哪个属性做 key
    const keyName = viewLevel === 'neighbourhood'
    ? feature.properties.neighbourhood      // 小区层级，用 neighbourhood
    : feature.properties.neighbourhood_group; // 大区层级，用 neighbourhood_group
    // const groupName = feature.properties.neighbourhood_group;

    // const district = feature.properties.neighbourhood_group;
    const stats = getDistrictStats();
    const district = feature.properties.neighbourhood_group;

    const districtStats = stats[keyName] || {
      count: 0, avgPrice: 0, minPrice: 0, maxPrice: 0, totalReviews: 0, popularity: 0
    };

    if (feature.properties) {
      const popupContent = `
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-width: 280px;">
           <h4>📍 ${
                 viewLevel === 'neighbourhood'
                   ? feature.properties.neighbourhood
                   : feature.properties.neighbourhood_group
               }</h4>
          <p style="margin: 0 0 8px 0; color: #7f8c8d; font-size: 14px; font-weight: 500;">
            🏛️ ${district}
          </p>
          <div style="background: #f8f9fa; padding: 12px; border-radius: 8px; margin: 8px 0;">
            <div style="margin: 4px 0; font-size: 14px;">
              <span style="color: #495057;">🏠 Listing Count:</span> 
              <strong style="color: #007bff;">${districtStats.count.toLocaleString()}</strong>
            </div>
            ${districtStats.count > 0 ? `
              <div style="margin: 4px 0; font-size: 14px;">
                <span style="color: #495057;">💰 Average Price:</span> 
                <strong style="color: #28a745;">€${districtStats.avgPrice}</strong>
              </div>
              <div style="margin: 4px 0; font-size: 14px;">
                <span style="color: #495057;">📊 Price Range:</span> 
                <strong style="color: #6c757d;">€${districtStats.minPrice} - €${districtStats.maxPrice}</strong>
              </div>
              <div style="margin: 4px 0; font-size: 14px;">
                <span style="color: #495057;">⭐ Total Reviews:</span> 
                <strong style="color: #ffc107;">${districtStats.totalReviews.toLocaleString()}</strong>
              </div>
              <div style="margin: 4px 0; font-size: 14px;">
                <span style="color: #495057;">🔥 Popularity:</span> 
                <strong style="color: #e83e8c;">${districtStats.popularity}%</strong>
              </div>
            ` : '<div style="color: #6c757d; font-size: 14px;">No listing data available</div>'}
          </div>
          
          ${districtStats.count > 0 ? `
            <div style="margin-top: 12px; display: flex; gap: 8px;">
              <button 
                onclick="window.confirmDistrictSelection && window.confirmDistrictSelection('${district}', ${JSON.stringify({level: 'boundary', stats: districtStats}).replace(/"/g, '&quot;')})"
                style="
                  flex: 1;
                  padding: 8px 12px;
                  background: #28a745;
                  color: white;
                  border: none;
                  border-radius: 4px;
                  font-size: 12px;
                  cursor: pointer;
                  font-weight: bold;
                "
                onmouseover="this.style.background='#1e7e34'"
                onmouseout="this.style.background='#28a745'"
              >
                ✅ Select ${district} CC
              </button>
            </div>
          ` : ''}
          
          <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #ecf0f1; text-align: center;">
            <small style="color: #6c757d;">💡 Click boundary to select, or use the confirm button above</small>
          </div>
        </div>
      `;
      layer.bindPopup(popupContent);
    }

    layer.on({
      mouseover: (e: any) => {
        const lyr = e.target;

        // 取消正在等待的反高亮
        cancelUnhighlight();

        // 如果之前高亮的是别的图层，先复原它
        if (hoverRef.current.layer && hoverRef.current.layer !== lyr) {
          resetLayerStyle(hoverRef.current.layer, hoverRef.current.layer.feature);
        }

        // 记录并高亮当前图层
        hoverRef.current.layer = lyr;
        highlightLayer(lyr);

        // === Hover 信息改为使用 marker 数据 ===
        const props = feature.properties;
        const name = (viewLevel === 'neighbourhood') ? props.neighbourhood : props.neighbourhood_group;
        const clientX = (e.originalEvent?.clientX) || 0;
        const clientY = (e.originalEvent?.clientY) || 0;
        const areaFromMarker = getAreaFromMarker(name, props.neighbourhood_group);
        if (areaFromMarker) {
          onGeometryEnter?.(areaFromMarker, { x: clientX, y: clientY });
        }
      },
      mouseout: (e: any) => {
        const lyr = e.target;

        // 1) 仍在该要素内部（同一 SVG 容器或 MultiPolygon 子 path）→ 忽略
        const el = lyr.getElement?.();
        const rt = e.originalEvent?.relatedTarget as HTMLElement | null;
        if (el && rt && el.contains(rt)) {
          return;
        }

        // 2) 仍在该要素包围盒内（跨边界/内洞时常见）→ 忽略
        try {
          if (e.latlng && lyr.getBounds && lyr.getBounds().contains(e.latlng)) {
            return;
          }
        } catch {}

        // 3) 延迟复原（轮询式），真正离开后才 onGeometryLeave
        scheduleUnhighlight(lyr, feature, () => {
          if (selectedDistrict !== feature.properties.neighbourhood_group) {
            onGeometryLeave?.();
          }
        });
      },
      click: (e: any) => {
        // In neighbourhood view, clicking a polygon should NOT close the modal.
        if (viewLevel !== 'neighbourhood') return;

        const clickedName = (viewLevel === 'neighbourhood' && feature?.properties?.neighbourhood) || feature.properties.neighbourhood_group;
        console.log('🗺️ Neighbourhood clicked:', clickedName);

        // Update selection to drive Overview changes, similar to district behaviour
        if (onDistrictClick) {
          const stats = getDistrictStats();
          onDistrictClick(clickedName, {
            feature,
            stats: stats[clickedName] || {},
            allStats: stats,
            shouldZoom: enableAutoZoom
          });
        }
        if (enableAutoZoom) {
          setTimeout(() => {
            const map = e.target._map;
            map?.fitBounds(e.target.getBounds(), { padding:[40,40], maxZoom:13, animate:true, duration:0.5 });
          }, 50);
        }
        e.target.openPopup();
      }

    });
  };

  // 🆕 设置全局确认函数
  useEffect(() => {
    window.confirmDistrictSelection = (districtName, data) => {
      if (onConfirmSelection) {
        onConfirmSelection(districtName, data);
      }
    };
    
    return () => {
      delete window.confirmDistrictSelection;
    };
  }, [onConfirmSelection]);

  if (!geojsonData) return null;

  const geoJsonKey = `${selectedDistrict}-${heatmapMode}-${heatmapEnabled}-${districtsData?.length || 0}`;

  return (
    <AnyGeoJSON
      key={geoJsonKey}
      data={geojsonData}
      style={getNeighbourhoodStyle}
      onEachFeature={onEachFeature}
      pane="choroplethPane"
    />
  );
};

// 快速推荐组件 - 保持不变
const QuickRecommendations = ({ districtsData, onDistrictSelect, loading  }: { districtsData: any[] | null; onDistrictSelect: (name: string) => void; loading: boolean }) => {
    if (loading) {
      return (
        <div className="bg-white p-3 rounded-lg border border-gray-200">
          <div className="text-sm font-medium text-gray-700 mb-2">🎯 Quick Recommendations</div>
          <div className="flex items-center justify-center py-4">
            <div className="animate-pulse flex space-x-2">
              <div className="rounded bg-gray-200 h-6 w-16"></div>
              <div className="rounded bg-gray-200 h-6 w-20"></div>
              <div className="rounded bg-gray-200 h-6 w-18"></div>
            </div>
          </div>
        </div>
      );
    }
  
  if (!districtsData || districtsData.length === 0) return null;

  // 基于不同维度的推荐
  const recommendations = {
    budget: districtsData.filter(d => d.avg_price < 80).slice(0, 3),
    popular: districtsData.sort((a, b) => b.popularity_score - a.popularity_score).slice(0, 3),
    balanced: districtsData.filter(d => d.avg_price >= 60 && d.avg_price <= 100 && d.popularity_score > 10).slice(0, 3)
  };

  return (
    <div className="bg-white p-3 rounded-lg border border-gray-200">
      <div className="text-sm font-medium text-gray-700 mb-2">🎯 Quick Recommendations</div>
      
      <div className="space-y-2">
        <div>
          <div className="text-xs text-gray-600 mb-1">💰 Budget-Friendly (Under €80)</div>
          <div className="flex flex-wrap gap-1">
            {recommendations.budget.map(district => (
              <button
                key={district.name}
                onClick={() => onDistrictSelect(district.name)}
                className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors"
              >
                {district.name.replace(' - ', '-')} (€{district.avg_price})
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs text-gray-600 mb-1">🔥 Most Popular</div>
          <div className="flex flex-wrap gap-1">
            {recommendations.popular.map(district => (
              <button
                key={district.name}
                onClick={() => onDistrictSelect(district.name)}
                className="px-2 py-1 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200 transition-colors"
              >
                {district.name.replace(' - ', '-')} ({district.popularity_score}%)
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs text-gray-600 mb-1">⚖️ Best Balance</div>
          <div className="flex flex-wrap gap-1">
            {recommendations.balanced.map(district => (
              <button
                key={district.name}
                onClick={() => onDistrictSelect(district.name)}
                className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
              >
                {district.name.replace(' - ', '-')}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};



// 🔧 主要的热力图Modal组件 - 修复所有问题
const BerlinHeatmapModal = ({ open, onClose, onDistrictSelect, shouldSendMessageOnSelect = true }: { open: boolean; onClose: () => void; onDistrictSelect?: (info: any) => void; shouldSendMessageOnSelect?: boolean }) => {
  // 🆕 两级视图状态管理
  const [viewLevel, setViewLevel] = useState<'neighbourhood_group' | 'neighbourhood'>('neighbourhood_group');
  const [parentDistrict, setParentDistrict] = useState<string | null>(null);
  
  // 原有状态保持不变
  const [geojsonData, setGeojsonData] = useState<any | null>(null);
  const [districtsData, setDistrictsData] = useState<any[] | null>(null);
  const [markersData, setMarkersData] = useState<any[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDistrict, setSelectedDistrict] = useState<string>('all');
  const [showBoundaries, setShowBoundaries] = useState<boolean>(true);
  const [showMarkers, setShowMarkers] = useState<boolean>(true);
  const [heatmapMode, setHeatmapMode] = useState<'count' | 'price' | 'popularity'>('count');
  const [heatmapEnabled, setHeatmapEnabled] = useState<boolean>(false);
  const [enableAutoZoom, setEnableAutoZoom] = useState<boolean>(true);
  const [shouldFitBounds, setShouldFitBounds] = useState<boolean>(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'overview'|'controls'|'insights'>('overview');
  // 🌈 渐变热力图（基于 markers）控制
  const [pointHeatEnabled, setPointHeatEnabled] = useState<boolean>(true);
  const [pointHeatRadius, setPointHeatRadius] = useState<number>(12);
  const [pointHeatBlur, setPointHeatBlur] = useState<number>(28);
  const [pointHeatMode, setPointHeatMode] = useState<'count' | 'price' | 'popularity'>('count');
  // �� 服务器原始点热力
  const [heatPoints, setHeatPoints] = useState<any[] | null>(null);
  const [heatLoading, setHeatLoading] = useState<boolean>(false);
  const [showDots, setShowDots] = useState<boolean>(true);
  const dotsRendererRef = useRef<any | null>(null);
  useEffect(() => {
    if (!dotsRendererRef.current) {
      try { dotsRendererRef.current = (L as any).canvas({ padding: 0.5 }); } catch {}
    }
  }, []);

  const sampledDotFeatures = useMemo<any[]>(() => {
    if (!showDots || !Array.isArray(heatPoints)) return [] as any[];
    const N = heatPoints.length;
    const MAX = 8000;
    const stride = Math.max(1, Math.ceil(N / MAX));
    const features: any[] = [];
    for (let i = 0; i < N; i += stride) {
      const p = heatPoints[i];
      const arr = Array.isArray(p);
      const latVal = arr ? p[0] : p?.lat;
      const lngVal = arr ? p[1] : p?.lng;
      const wtVal = arr ? p?.[2] : (p?.weight ?? 1);
      const rtcVal = arr ? p?.[3] : (p?.room_type_code ?? p?.rt ?? 0);
      const lat = Number(latVal);
      const lng = Number(lngVal);
      const rtc = Number(rtcVal) || 0;
      const w = Number(wtVal) || 1;
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lng, lat] },
        properties: { rtc, w }
      });
    }
    return features;
  }, [heatPoints, showDots]);

  const weightBy = (() => {
    if (heatmapMode === 'price') return 'price';
    if (heatmapMode === 'popularity') return 'reviews';
    return 'uniform';
  })();

  const [districtsLoading, setDistrictsLoading] = useState(false);
  // const [markersLoading, setMarkersLoading] = useState(false);

  // 🆕 悬浮提示状态
  const [hoverInfo, setHoverInfo] = useState<{ visible: boolean; area: any; position: { x: number; y: number } | null}>({
    visible: false,
    area: null,
    position: null
  });
  // hover coordination in parent (adjust delay)
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isOverGeometryRef = useRef<boolean>(false);
  const isOverCardRef = useRef<boolean>(false);
  const scheduleShowHover = (area: any, position: { x: number; y: number }) => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    hoverTimerRef.current = setTimeout(() => {
      if (isOverGeometryRef.current || isOverCardRef.current) {
        setHoverInfo({ visible: true, area, position });
      }
    }, 250);
  };
  const cancelHoverTimer = () => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
  };
  const maybeHideHover = () => {
    if (!isOverGeometryRef.current && !isOverCardRef.current) {
      setHoverInfo({ visible: false, area: null, position: null });
    }
  };

  const [filters] = useState<{ price_min: number | null; price_max: number | null; room_type: string | null; min_reviews: number }>({
    price_min: null,
    price_max: null,
    room_type: null,
    min_reviews: 0
  });

  const districts = [
    'all',
    'Charlottenburg-Wilm.',
    'Friedrichshain-Kreuzberg',
    'Lichtenberg',
    'Marzahn - Hellersdorf',
    'Mitte',
    'Neukölln',
    'Pankow',
    'Reinickendorf',
    'Spandau',
    'Steglitz - Zehlendorf',
    'Tempelhof - Schöneberg',
    'Treptow - Köpenick'
  ];

  const getDistrictBorderColor = (district: string) => {
    const districtColors: Record<string, string> = {
      'Mitte': '#e74c3c',
      'Friedrichshain-Kreuzberg': '#9b59b6', 
      'Charlottenburg-Wilm.': '#3498db',
      'Pankow': '#1abc9c',
      'Tempelhof - Schöneberg': '#f39c12',
      'Neukölln': '#2ecc71',
      'Steglitz - Zehlendorf': '#e67e22',
      'Spandau': '#34495e',
      'Reinickendorf': '#8e44ad',
      'Lichtenberg': '#16a085',
      'Marzahn - Hellersdorf': '#d35400',
      'Treptow - Köpenick': '#27ae60'
    };
    
    return districtColors[district] || '#7f8c8d';
  };

  // 🔧 修复：简化的导航处理函数 - 确保状态正确更新  
  const handleNavigation = (newLevel: 'neighbourhood_group' | 'neighbourhood', districtName: string | null) => {
    console.log('🧭 开始导航:', { 
      from: { level: viewLevel, parent: parentDistrict },
      to: { level: newLevel, parent: districtName }
    });
    
    // 清除UI状态
    setHoverInfo({ visible: false, area: null, position: null });
    setSelectedDistrict('all');
    
    // �� 修复：立即更新状态，不要异步
    setViewLevel(newLevel);
    setParentDistrict(districtName);
    
    console.log('✅ 状态已更新，准备加载数据...');
    
    // 立即开始加载新数据
    setTimeout(() => {
      console.log('🔄 开始加载新层级数据:', newLevel, districtName);
      loadAllMapData(newLevel, districtName);
    }, 100);
  };

  // 🆕 添加：筛选条件变化时自动刷新标记
  useEffect(() => {
    if (open && geojsonData && markersData) {
      console.log('🔍 筛选条件变化，重新加载标记数据');
      loadMarkersData();
    }
  }, [filters.price_min, filters.price_max, filters.room_type, filters.min_reviews]);

  // 🔧 修复：优化的批量数据加载 - 增强调试和错误处理
  const loadAllMapData = async (level = viewLevel, districtName = parentDistrict) => {
    console.log('🔄 批量数据加载开始:', { 
      level, 
      districtName, 
      currentViewLevel: viewLevel,
      currentParent: parentDistrict 
    });
    
    setIsLoading(true);
    
    try {
      // 🔧 修复：确保使用正确的参数，而不是当前状态
      console.log('📋 准备加载区域数据...');
      await loadDistrictsData(level, districtName);
      
      console.log('📋 准备加载标记数据...');
      await loadMarkersData(level, districtName);
      
      console.log('📋 准备加载热力点数据...');
      await loadServerHeatPoints(level, districtName);
      
      console.log('🎉 批量数据加载完成');
      
    } catch (err) {
      console.error('❌ 批量数据加载失败:', err);
      const message = (err as any)?.message || String(err);
      setError(`数据加载失败: ${message}`);
    } finally {
      setIsLoading(false);
      console.log('🏁 数据加载流程结束');
    }
  };

  // 🆕 确认选择处理
  const handleConfirmSelection = async (districtName: string, selectionData: any) => {
    console.log('✅ 确认选择区域:', districtName, selectionData);
    
    // 1) 先告诉后端
    try {
      await selectArea(
        selectionData.level || viewLevel, districtName
      )
      console.log('🟢 selectArea API 成功')
    } catch (err) {
      console.error('🔴 selectArea API 失败', err)
    }

    if (onDistrictSelect) {
      const districtInfo = {
        name: districtName,
        level: selectionData.level || viewLevel,
        parent: selectionData.parent || (viewLevel === 'neighbourhood' ? parentDistrict : null),
        stats: selectionData.stats || {},
        selectedAt: new Date().toISOString(),
        source: 'user_confirmation',
        isConfirmed: true, // 🔥 标记为用户确认选择
        // 🆕 将是否应发送消息的偏好带回上层
        shouldSendMessage: !!shouldSendMessageOnSelect
      };
      console.log('🔍 传递给 App 的 districtInfo:', districtInfo);
      onDistrictSelect(districtInfo);
    }
  };

  useEffect(() => {
    if (open && !geojsonData) {
      loadMapData();
    }
  }, [open]);

  useEffect(() => {
    if (open && geojsonData) {
      // 首次地理数据就绪或筛选/模式变更时再拉取统计与标记
      loadDistrictsData();
      loadMarkersData();
      loadServerHeatPoints();
    }
  }, [filters, heatmapMode, geojsonData, heatmapEnabled, viewLevel, parentDistrict, pointHeatEnabled, showDots]);

  const loadMapData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // 仅加载地理数据，其它数据由后续 effect 触发，避免重复请求
      const geoDataResult = await loadGeojsonData();
      setGeojsonData(geoDataResult);
      console.log('📊 地图数据加载完成');
      
    } catch (err) {
      console.error('Error loading map data:', err);
      setError('Unable to load map data. Please check network connection and data source');
    } finally {
      setIsLoading(false);
    }
  };

  const loadGeojsonData = async () => {
    try {
      const response = await fetch('/neighbourhoods.geojson');
      if (!response.ok) throw new Error('Unable to load geographic data file');
      return await response.json();
    } catch (err) {
      console.warn('🚨 Using mock geographic data, please add real neighbourhoods.geojson file');
      
      return err;
    }
  };

  // 🔧 修复：增强的区域数据加载函数 - 改善错误处理
  const loadDistrictsData = async (level = viewLevel, districtName = parentDistrict) => {
    try {
      setDistrictsLoading(true);
      setError(null);
      
      console.log(`🔍 加载${level}区域数据:`, districtName || 'ALL');
      console.log('📋 当前筛选条件:', filters);
      
      const requestParams: any = { ...filters };
      // 告诉后端当前层级
      requestParams.level = level;
      if (level === 'neighbourhood' && districtName) {
        requestParams.district_name = districtName as string;
      }
      
      console.log('📤 发送区域数据请求参数:', requestParams);
      
      const result: any = await fetchDistrictStats(requestParams);
      
      console.log('📬 区域数据API响应:', result);
      
      // 选择正确数组名并标准化字段
      const rawList = (
        level === 'neighbourhood'
          ? (result.neighbourhoods || result.areas || result.items || result.districts)
          : (result.districts || result.items || result.neighbourhoods)
      ) || [];

      const toNum = (v: any) => (v == null || v === '' ? 0 : (typeof v === 'number' ? v : Number(v)));

      const normalized = rawList.map((it: any) => ({
        name: it.name ?? (level === 'neighbourhood' ? (it.neighbourhood || it.area_name) : (it.neighbourhood_group || it.district)),
        listing_count: toNum(it.listing_count ?? it.count),
        avg_price: toNum(it.avg_price ?? it.average_price),
        min_price: toNum(it.min_price ?? it.price_min),
        max_price: toNum(it.max_price ?? it.price_max),
        total_reviews: toNum(it.total_reviews ?? it.reviews),
        popularity_score: toNum(it.popularity_score ?? it.popularity),
        heat_intensity: it.heat_intensity ?? {
          count: toNum(it.heat_count),
          price: toNum(it.heat_price),
          popularity: toNum(it.heat_popularity)
        }
      }));

      // 兜底：如果小层级没返回，聚合 marker 数据
      if (level === 'neighbourhood' && normalized.length === 0 && Array.isArray(markersData)) {
        const fallback = markersData.map((m: any) => ({
          name: m.district,
          listing_count: toNum(m.popup_info?.listing_count),
          avg_price: toNum(m.popup_info?.avg_price),
          min_price: toNum(m.popup_info?.min_price),
          max_price: toNum(m.popup_info?.max_price),
          total_reviews: toNum(m.popup_info?.total_reviews),
          popularity_score: toNum(m.popup_info?.popularity_percentage),
          heat_intensity: { count: 0, price: 0, popularity: 0 }
        }));
        setDistrictsData(fallback);
        console.warn('ℹ️ 使用 marker 数据作为 neighbourhood 统计兜底');
      } else {
        setDistrictsData(normalized);
        console.log('✅ 区域数据加载成功（标准化后）:', normalized.length, '条');
      }
      
    } catch (err) {
      console.warn('🚨 区域数据API请求失败，使用模拟数据:', (err as any)?.message);
      setError(`API Error: ${(err as any)?.message || String(err)}`);
      
      // 🔄 降级到模拟数据
      console.log('📋 生成模拟区域数据 - level:', level, 'district:', districtName);
      
    } finally {
      setDistrictsLoading(false);
    }
  };

  // 🔧 修复：增强的标记数据加载函数 - 改善错误处理
  const loadMarkersData = async (level = viewLevel, districtName = parentDistrict) => {
    try {
      // setMarkersLoading(true);
      setError(null);
      
      console.log(`🔍 加载${level}标记数据:`, districtName || 'ALL');
      console.log('📋 当前筛选条件:', filters);
      
      // 🆕 构建API请求参数
      const requestParams: any = { 
        level,
        ...filters // 应用当前的筛选条件
      };
      
      // 如果是小区域层级，添加大区域名称
      if (level === 'neighbourhood' && districtName) {
        requestParams.district_name = districtName;
      }
      
      console.log('📤 发送请求参数:', requestParams);
      
      // 🆕 调用真实API
      const result: any = await fetchMapMarkers(requestParams);
      
      console.log('📬 API响应:', result);
      
      if (result.success && Array.isArray(result.markers)) {
        setMarkersData(result.markers);
        console.log('✅ 标记数据加载成功:', result.markers.length, '个标记');
        
        // 🔧 修复：如果API返回空数据，记录警告但不抛出错误
        if (result.markers.length === 0) {
          console.warn('⚠️ API返回空标记数据，可能是正常情况');
        }
      } else {
        console.warn('⚠️ API返回数据格式异常:', result);
        throw new Error('Invalid markers data format from API');
      }
      
    } catch (err) {
      console.warn('🚨 API请求失败，使用模拟数据:', (err as any)?.message);
      setError(`API Error: ${(err as any)?.message || String(err)}`);
      
      // 🔄 降级到模拟数据
      console.log('📋 生成模拟标记数据 - level:', level, 'district:', districtName);
  
    } // finally {
      // setMarkersLoading(false);
    // }
  };

  // 🔧 修复：标记悬浮处理 - 改善清除逻辑
  const handleMarkerHover = (marker: any, event: any, action: string) => {
    if (action === 'hover' && marker) {
      isOverGeometryRef.current = true;
      scheduleShowHover(
        {
          name: marker.district,
          listing_count: marker.popup_info.listing_count,
          avg_price: marker.popup_info.avg_price,
          total_reviews: marker.popup_info.total_reviews,
          popularity_score: marker.popup_info.popularity_percentage,
          parent: marker.parent_district
        },
        { x: event.originalEvent.clientX, y: event.originalEvent.clientY }
      );
    } else {
      isOverGeometryRef.current = false;
      cancelHoverTimer();
      maybeHideHover();
    }
  };

  // 🔧 修复：增强的标记点击处理 - 添加详细调试和确保状态更新
 // 1️⃣ 点击数字标记时
  const handleMarkerClick = (
    districtName: string, 
    markerData: any, 
    isLargeDistrict: boolean
  ) => {
    console.log('🚀 标记点击处理开始:', {
      districtName,
      isLargeDistrict,
      currentViewLevel: viewLevel,
      markerData
    });

    // 清除悬浮
    setHoverInfo({ visible: false, area: null, position: null });

    if (isLargeDistrict && viewLevel === 'neighbourhood_group') {
      // 在大区层级下，点击数字标记仅更新概览所需的选中名称，不改变导航或标签页
      setSelectedDistrict(districtName);
      return;
    } else {
      // 小区直接选中
      setSelectedDistrict(districtName);
      // ⭐➞ 切到 Insights 面板
      // setActiveTab('insights'); // 注释：临时移除 insights
    }
  };

// 2️⃣ 点击多边形边界时
  const handleDistrictClick = (
    districtName: string, 
    additionalData: { shouldZoom?: boolean; stats?: any; feature?: any }
  ) => {
    console.log('🗺️ 区域点击:', districtName);

    setSelectedDistrict(districtName);

    // Behaviour: In neighbourhood view, clicking a neighbourhood should not close modal or confirm selection.
    // Keep Overview responsive by switching to insights, but DO NOT call confirm selection here when in neighbourhood view.
    // setActiveTab('insights'); // 注释：临时移除 insights

    // 查找当前区的统计数据
    const stats = districtsData?.find((d: any) => d.name === districtName)?.stats || {};
    console.log('🔍 当前区统计数据:', stats);

    // Only auto-confirm selection for district-level interactions
    if (viewLevel === 'neighbourhood_group') {
      handleConfirmSelection(districtName, { 
        stats, 
        level: 'neighbourhood_group', 
        ...additionalData 
      });
    }
    
    if (enableAutoZoom && additionalData?.shouldZoom !== false) {
      setShouldFitBounds(true);
    }
  };


  const handleDistrictChange = (district: string) => {
    setSelectedDistrict(district);
    if (district !== 'all') {
      handleDistrictClick(district, { stats: {}, feature: null, shouldZoom: enableAutoZoom });
    }
  };

  const handleHeatmapModeChange = (mode: 'count' | 'price' | 'popularity') => {
    setHeatmapMode(mode);
    console.log('🎨 热力图模式切换:', mode);
  };

  const handleHeatmapToggle = (enabled: boolean) => {
    setHeatmapEnabled(enabled);
    console.log('🔥 热力图开关:', enabled ? '开启' : '关闭');
  };

  // 🆕 加载服务端热力点
  const loadServerHeatPoints = async (level = viewLevel, districtName = parentDistrict) => {
    if (!pointHeatEnabled && !showDots) { setHeatPoints([]); return; }
    try {
      setHeatLoading(true);
      const params: any = {
        level: level === 'neighbourhood' ? 'neighbourhood' : 'neighbourhood_group',
        price_min: filters.price_min,
        price_max: filters.price_max,
        room_type: filters.room_type,
        min_reviews: filters.min_reviews,
        weight_by: weightBy,
        max_points: 20000,
        format: 'json'
      };
      if (params.level === 'neighbourhood' && districtName) {
        params.district_name = districtName;
      }
      const res: any = await fetchHeatPoints(params);
      const pts = Array.isArray(res?.points) ? res.points : [];
      setHeatPoints(pts);
    } catch (e) {
      console.warn('🚨 loadServerHeatPoints failed:', e);
      setHeatPoints([]);
    } finally {
      setHeatLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black bg-opacity-60">
      <div className="bg-white rounded-lg shadow-2xl w-[95vw] h-[90vh] mx-4 flex flex-col overflow-hidden">
        
        {/* 🆕 面包屑导航 */}
        <BreadcrumbNavigation 
          viewLevel={viewLevel}
          parentDistrict={parentDistrict}
          onNavigate={handleNavigation}
        />
        
        {/* 🆕 快速返回按钮 - 仅在小区域视图显示 */}
        {viewLevel === 'neighbourhood' && parentDistrict && (
          <div className="bg-blue-50 px-4 py-2 border-b border-blue-200 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-blue-700">
              <span>🏘️ Exploring neighbourhoods in <strong>{parentDistrict}</strong></span>
            </div>
            <button
              onClick={() => handleNavigation('neighbourhood_group', null)}
              className="text-blue-600 hover:text-blue-800 text-sm font-medium px-3 py-1 rounded-md hover:bg-blue-100 transition-colors flex items-center gap-1"
            >
              ← Back to Districts
            </button>
          </div>
        )}
        
        <div className="flex flex-1 overflow-hidden">
          {/* 可折叠的侧边栏 - 保持原样 */}
          <div className={`${sidebarCollapsed ? 'w-12' : 'w-80'} bg-gray-50 border-r border-gray-200 flex flex-col transition-all duration-300`}>
            {/* 侧边栏头部 */}
            <div className="p-4 border-b border-gray-200 bg-white">
              {!sidebarCollapsed ? (
                <>
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-bold text-gray-800">
                      🗺️ {viewLevel === 'neighbourhood_group' ? 'District Explorer' : `${parentDistrict} Areas`}
                    </h3>
                    <button
                      onClick={() => setSidebarCollapsed(true)}
                      className="text-gray-400 hover:text-gray-600 p-1 rounded"
                      title="Collapse sidebar"
                    >
                      ←
                    </button>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">
                    {viewLevel === 'neighbourhood_group' 
                      ? 'Discover Berlin neighborhoods for your stay' 
                      : `Explore neighbourhoods in ${parentDistrict}`
                    }
                  </p>
                </>
              ) : (
                <button
                  onClick={() => setSidebarCollapsed(false)}
                  className="w-full text-gray-600 hover:text-gray-800 p-1 rounded text-center"
                  title="Expand sidebar"
                >
                  →
                </button>
              )}
            </div>

            {!sidebarCollapsed && (
              <>
                {/* 标签页导航 */}
                <div className="flex border-b border-gray-200 bg-white">
                  <button
                    onClick={() => setActiveTab('overview')}
                    className={`flex-1 px-3 py-2 text-sm font-medium ${
                      activeTab === 'overview'
                        ? 'text-blue-600 border-b-2 border-blue-600'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    📈 Overview
                  </button>
                  <button
                    onClick={() => setActiveTab('controls')}
                    className={`flex-1 px-3 py-2 text-sm font-medium ${
                      activeTab === 'controls'
                        ? 'text-blue-600 border-b-2 border-blue-600'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    🎛️ Controls
                  </button>
                  {/* <button
                    onClick={() => setActiveTab('insights')}
                    className={`flex-1 px-3 py-2 text-sm font-medium ${
                      activeTab === 'insights'
                        ? 'text-blue-600 border-b-2 border-blue-600'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    📊 Insights
                  </button> */}
                </div>
                
                {/* 标签页导航 */}
                {/* <div className="flex border-b border-gray-200 bg-white">
                  {['overview','controls','insights'].map(tab => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab as any)}
                      className={`flex-1 px-3 py-2 text-sm font-medium ${
                        activeTab === tab 
                          ? 'text-blue-600 border-b-2 border-blue-600' 
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      {{
                        overview: '🏠 Overview',
                        controls: '🎛️ Controls',
                        insights: '📊 Insights'
                      }[tab]}
                    </button>
                  ))}
                </div> */}
                
                {/* 侧边栏内容 */}
                <div className="flex-1 overflow-y-auto p-4">
                  {activeTab === 'overview' && (
                    // 新增全局概览面板，传入最新的 districtsData
                    <OverviewPanel 
                      districtsData={districtsLoading ? [] : districtsData || []}
                      selectedName={selectedDistrict}
                      level={viewLevel === 'neighbourhood' ? 'neighbourhood' : 'district'}
                      budgetMin={filters.price_min}
                      budgetMax={filters.price_max}
                      onDrillDown={() => {
                        // setSelectedInsight(key) // Removed as per edit hint
                        // setActiveTab('insights')
                      }}
                      //setActiveTab={setActiveTab} 
                    />
                  )} 
                  
                  {activeTab === 'controls' && (
                    <div className="space-y-4">
                      {/* 快速推荐 */}
                      <QuickRecommendations 
                        districtsData={districtsLoading ? null : districtsData} 
                        onDistrictSelect={handleDistrictChange}
                        loading={districtsLoading}
                      />

                      {/* 区域选择 */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          🏘️ Select {viewLevel === 'neighbourhood_group' ? 'District' : 'Neighbourhood'}
                        </label>
                        <select 
                          value={selectedDistrict}
                          onChange={(e) => handleDistrictChange(e.target.value)}
                          className="w-full p-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="all">🌍 Show All {viewLevel === 'neighbourhood_group' ? 'Districts' : 'Neighbourhoods'}</option>
                          {districtsData && districtsData.map(district => (
                            <option key={district.name} value={district.name}>
                              📍 {district.name}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* 显示控制 */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-700 mb-2">👁️ Display</div>
                        <div className="space-y-2">
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">District Boundaries</span>
                            <input
                              type="checkbox"
                              checked={showBoundaries}
                              onChange={(e) => setShowBoundaries(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Number Markers</span>
                            <input
                              type="checkbox"
                              checked={showMarkers}
                              onChange={(e) => setShowMarkers(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Auto Zoom</span>
                            <input
                              type="checkbox"
                              checked={enableAutoZoom}
                              onChange={(e) => setEnableAutoZoom(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                        </div>
                      </div>


                      {/* 🌈 渐变热力图（markers） */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-700 mb-2">�� Data Layers</div>
                        <div className="space-y-2">
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Enable Gradient Heat</span>
                            <input
                              type="checkbox"
                              checked={pointHeatEnabled}
                              onChange={(e) => setPointHeatEnabled(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Enable Area Coloring</span>
                            <input
                              type="checkbox"
                              checked={heatmapEnabled}
                              onChange={(e) => handleHeatmapToggle(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Show Raw Dots (server points)</span>
                            <input
                              type="checkbox"
                              checked={showDots}
                              onChange={(e) => setShowDots(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                        </div>
                        {pointHeatEnabled && (
                          <div className="space-y-2 pt-2">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-gray-600">Radius</span>
                              <input type="range" min={15} max={80} step={1} value={pointHeatRadius} onChange={(e) => setPointHeatRadius(Number(e.target.value))} className="w-40" />
                              <span className="text-xs text-gray-500 w-8 text-right">{pointHeatRadius}</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-gray-600">Blur</span>
                              <input type="range" min={8} max={50} step={1} value={pointHeatBlur} onChange={(e) => setPointHeatBlur(Number(e.target.value))} className="w-40" />
                              <span className="text-xs text-gray-500 w-8 text-right">{pointHeatBlur}</span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* 🆕 调试信息面板 */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-700 mb-2">🐛 Debug Info</div>
                        <div className="text-xs text-gray-600 space-y-1">
                          <div>Level: <span className="font-mono">{viewLevel}</span></div>
                          <div>Parent: <span className="font-mono">{parentDistrict || 'null'}</span></div>
                          <div>Selected: <span className="font-mono">{selectedDistrict}</span></div>
                          <div>Districts: <span className="font-mono">{districtsData?.length || 0}</span></div>
                          <div>Markers: <span className="font-mono">{markersData?.length || 0}</span></div>
                          <div>Loading: <span className="font-mono">{isLoading ? 'true' : 'false'}</span></div>
                        </div>
                      </div>

                      {/* 行政区域颜色图例 */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-700 mb-2">🎨 District Colors</div>
                        <div className="grid grid-cols-2 gap-1 text-xs">
                          {districts.slice(1, 7).map(district => (
                            <div key={district} className="flex items-center gap-1">
                              <div 
                                className="w-3 h-3 rounded border"
                                style={{ backgroundColor: getDistrictBorderColor(district) }}
                              ></div>
                              <span className="text-gray-600 truncate">{district.replace(' - ', '-').replace('Charlottenburg-Wilm.', 'Charl-W')}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )} 
                    
                  {activeTab === 'controls' && (
                    <div className="space-y-4">
                      {/* 快速推荐 */}
                      <QuickRecommendations 
                        districtsData={districtsLoading ? null : districtsData} 
                        onDistrictSelect={handleDistrictChange}
                        loading={districtsLoading}
                      />

                      {/* 区域选择 */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          🏘️ Select {viewLevel === 'neighbourhood_group' ? 'District' : 'Neighbourhood'}
                        </label>
                        <select 
                          value={selectedDistrict}
                          onChange={(e) => handleDistrictChange(e.target.value)}
                          className="w-full p-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="all">🌍 Show All {viewLevel === 'neighbourhood_group' ? 'Districts' : 'Neighbourhoods'}</option>
                          {districtsData && districtsData.map(district => (
                            <option key={district.name} value={district.name}>
                              📍 {district.name}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* 显示控制 */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-700 mb-2">👁️ Display</div>
                        <div className="space-y-2">
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">District Boundaries</span>
                            <input
                              type="checkbox"
                              checked={showBoundaries}
                              onChange={(e) => setShowBoundaries(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Number Markers</span>
                            <input
                              type="checkbox"
                              checked={showMarkers}
                              onChange={(e) => setShowMarkers(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Auto Zoom</span>
                            <input
                              type="checkbox"
                              checked={enableAutoZoom}
                              onChange={(e) => setEnableAutoZoom(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                        </div>
                      </div>


                      {/* 🌈 渐变热力图（markers） */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-700 mb-2">�� Data Layers</div>
                        <div className="space-y-2">
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Enable Gradient Heat</span>
                            <input
                              type="checkbox"
                              checked={pointHeatEnabled}
                              onChange={(e) => setPointHeatEnabled(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Enable Area Coloring</span>
                            <input
                              type="checkbox"
                              checked={heatmapEnabled}
                              onChange={(e) => handleHeatmapToggle(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                          <label className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">Show Raw Dots (server points)</span>
                            <input
                              type="checkbox"
                              checked={showDots}
                              onChange={(e) => setShowDots(e.target.checked)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                        </div>
                        {pointHeatEnabled && (
                          <div className="space-y-2 pt-2">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-gray-600">Radius</span>
                              <input type="range" min={15} max={80} step={1} value={pointHeatRadius} onChange={(e) => setPointHeatRadius(Number(e.target.value))} className="w-40" />
                              <span className="text-xs text-gray-500 w-8 text-right">{pointHeatRadius}</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-gray-600">Blur</span>
                              <input type="range" min={8} max={50} step={1} value={pointHeatBlur} onChange={(e) => setPointHeatBlur(Number(e.target.value))} className="w-40" />
                              <span className="text-xs text-gray-500 w-8 text-right">{pointHeatBlur}</span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* 🆕 调试信息面板 */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-700 mb-2">🐛 Debug Info</div>
                        <div className="text-xs text-gray-600 space-y-1">
                          <div>Level: <span className="font-mono">{viewLevel}</span></div>
                          <div>Parent: <span className="font-mono">{parentDistrict || 'null'}</span></div>
                          <div>Selected: <span className="font-mono">{selectedDistrict}</span></div>
                          <div>Districts: <span className="font-mono">{districtsData?.length || 0}</span></div>
                          <div>Markers: <span className="font-mono">{markersData?.length || 0}</span></div>
                          <div>Loading: <span className="font-mono">{isLoading ? 'true' : 'false'}</span></div>
                        </div>
                      </div>

                      {/* 行政区域颜色图例 */}
                      <div className="bg-white p-3 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-700 mb-2">🎨 District Colors</div>
                        <div className="grid grid-cols-2 gap-1 text-xs">
                          {districts.slice(1, 7).map(district => (
                            <div key={district} className="flex items-center gap-1">
                              <div 
                                className="w-3 h-3 rounded border"
                                style={{ backgroundColor: getDistrictBorderColor(district) }}
                              ></div>
                              <span className="text-gray-600 truncate">{district.replace(' - ', '-').replace('Charlottenburg-Wilm.', 'Charl-W')}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )} 
                    
                  {/* {activeTab === 'insights' && (
                    <ChartBoard 
                      level={viewLevel === 'neighbourhood' ? 'neighbourhood' : 'district'}
                      groupName={selectedDistrict !== 'all' 
                                  ? selectedDistrict 
                                  : (parentDistrict || 'ALL')} 
                    />
                  )} */}
                </div>
              </>
            )}
          </div>

          {/* 地图主体 */}
          <div className="flex-1 flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-white">
              {/* 🔧 修复：动态标题，根据当前状态显示 */}
              <h2 className="text-xl font-bold text-gray-800">
                {viewLevel === 'neighbourhood_group' 
                  ? 'Berlin Administrative Districts' 
                  : `${parentDistrict} Neighbourhoods`
                }
                {selectedDistrict !== 'all' && (
                  <span className="text-sm font-normal text-blue-600 ml-2">
                    (Focused: {selectedDistrict})
                  </span>
                )}
              </h2>
              <div className="flex items-center gap-2">
                
                <div className="flex items-center gap-3">
                {/* 📊 数据统计显示 */}
                {isLoading || districtsLoading ? (
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                    <span>Loading {viewLevel === 'neighbourhood_group' ? 'districts' : 'neighbourhoods'}...</span>
                  </div>
                ) : error ? (
                  <div className="text-sm text-red-500 flex items-center gap-1">
                    <span>⚠️</span>
                    Using mock data
                  </div>
                ) : districtsData && districtsData.length > 0 ? (
                  <div className="text-sm text-gray-600 font-medium">
                    <span className="text-blue-600 font-bold">
                      {districtsData.reduce((sum, d) => sum + d.listing_count, 0).toLocaleString()}
                    </span>
                    {' '}listings across{' '}
                    <span className="text-green-600 font-bold">
                      {districtsData.length}
                    </span>
                    {' '}{viewLevel === 'neighbourhood_group' ? 'districts' : 'neighbourhoods'}
                  </div>
                ) : (
                  <div className="text-sm text-gray-400">
                    No data available
                  </div>
                )}
    
                {/* 🔄 刷新按钮 */}
                {!isLoading && !districtsLoading && (
                  <button
                    onClick={() => {
                      loadDistrictsData();
                      loadMarkersData();
                    }}
                    className="text-gray-400 hover:text-blue-600 p-1 rounded hover:bg-gray-100 transition-colors"
                    title="Refresh data"
                  >
                    🔄
                  </button>
                )}
                
                {/* ❌ 关闭按钮 */}
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-600 text-2xl font-bold w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
                >
                  ×
                </button>
              </div>

              
              </div>
            </div>

            <div className="flex-1 relative">
              {isLoading && (
                <div className="absolute inset-0 bg-white bg-opacity-90 flex items-center justify-center z-50">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <div className="text-gray-700 font-medium">
                      Loading {viewLevel === 'neighbourhood_group' ? 'district' : 'neighbourhood'} data...
                    </div>
                    <div className="text-gray-500 text-sm mt-1">
                      {viewLevel === 'neighbourhood_group' ? 'Analyzing Berlin districts' : `Exploring ${parentDistrict} areas`}
                    </div>
                  </div>
                </div>
              )}

              {error && (
                <div className="absolute inset-0 bg-white flex items-center justify-center z-50">
                  <div className="text-center p-8 max-w-md">
                    <div className="text-red-600 mb-4 text-4xl">⚠️</div>
                    <div className="text-red-600 font-medium mb-2 text-lg">Failed to Load Map</div>
                    <div className="text-red-500 text-sm mb-4 bg-red-50 p-3 rounded">{error}</div>
                    <button
                      onClick={loadMapData}
                      className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      🔄 Retry
                    </button>
                  </div>
                </div>
              )}

              {!isLoading && !error && (
                                 <AnyMapContainer
                   center={[52.5200, 13.4050]}
                   zoom={viewLevel === 'neighbourhood_group' ? 11 : 13}
                   style={{ height: '100%', width: '100%' }}
                   className="z-0"
                 >
                   <PanesSetup />
                   <AnyTileLayer
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      maxZoom={18}
                    />
                   
                   {/* 修改顺序：先渲染边界，再渲染热力层，让热力层在上面 */}
                   {showBoundaries && (
                                           <NeighbourhoodLayer  
                       geojsonData={geojsonData}
                       selectedDistrict={selectedDistrict}
                       districtsData={districtsData}
                       heatmapMode={heatmapMode}
                       heatmapEnabled={heatmapEnabled}
                       enableAutoZoom={enableAutoZoom}
                       onDistrictClick={handleDistrictClick}
                       getDistrictBorderColor={getDistrictBorderColor}
                       onConfirmSelection={handleConfirmSelection}
                       viewLevel={viewLevel}
                       setHoverInfo={setHoverInfo}
                       onGeometryEnter={(area: any, position: { x: number; y: number }) => {
                         isOverGeometryRef.current = true;
                         scheduleShowHover(area, position);
                       }}
                       onGeometryLeave={() => {
                         isOverGeometryRef.current = false;
                         cancelHoverTimer();
                         maybeHideHover();
                       }}
                       shouldHoldHighlight={() => (isOverGeometryRef.current || isOverCardRef.current)}
                       markersData={markersData}
                       pointHeatEnabled={pointHeatEnabled}
                     />
                   )}
                   
                   {/* 🔥 服务端热力点（取代原 markers 渐变热） */}
                   {pointHeatEnabled && heatPoints && heatPoints.length > 0 && (
                     <ServerHeatLayer
                       enabled={pointHeatEnabled}
                       points={heatPoints}
                       radius={pointHeatRadius}
                       blur={pointHeatBlur}
                     />
                   )}
                   {/* 🔵 服务器点的原始散点（轻量渲染） */}
                   {showDots && sampledDotFeatures.length > 0 && (
                     <AnyGeoJSON
                       data={{ type: 'FeatureCollection', features: sampledDotFeatures as any }}
                       renderer={dotsRendererRef.current}
                       pointToLayer={(feature: any, latlng: any) => {
                         const rtc = Number(feature?.properties?.rtc || 0);
                         // 颜色映射：1=Entire(橘红)、2=Private(橙黄)、3=Shared(紫/洋红)、4=Hotel(蓝绿)、0/其他=灰
                         const color = rtc === 1 ? '#f97316' /* orange */
                           : rtc === 2 ? '#f59e0b' /* amber */
                           : rtc === 3 ? '#a21caf' /* purple/magenta */
                           : rtc === 4 ? '#06b6d4' /* cyan */
                           : '#9ca3af'; /* gray */
                         // 可选：基于第三列权重轻微缩放
                         const w = feature?.properties?.w ? Number(feature.properties.w) : 1;
                         const r = Math.max(0.8, Math.min(2.0, 0.8 + (w - 1) * 0.2));
                         return L.circleMarker(latlng, {
                           radius: r,
                           color,
                           opacity: 0.35,
                           fillOpacity: 0.35,
                           pane: 'dotsPane'
                         } as any);
                       }}
                     />
                   )}
                   
                   {/* 🔧 修改：传递确认选择回调 */}
                  <DistrictMarkers
                    markersData={markersData}
                    onMarkerClick={handleMarkerClick}
                    onMarkerHover={handleMarkerHover}
                    showMarkers={showMarkers}
                    viewLevel={viewLevel}
                    onConfirmSelection={handleConfirmSelection}
                    onNavigate={handleNavigation}
                  />
                  
                  <MapController 
                    selectedDistrict={selectedDistrict}
                    geojsonData={geojsonData}
                    shouldFitBounds={shouldFitBounds}
                    setBoundsChanged={setShouldFitBounds}
                    viewLevel={viewLevel}
                    onLevelChange={handleNavigation}
                  />
                </AnyMapContainer>
              )}

              {/* 🆕 悬浮返回按钮 - 在小区域视图时显示 */}
              <FloatingBackButton 
                viewLevel={viewLevel}
                onNavigate={handleNavigation}
              />
            </div>
          </div>
        </div>
        
        {/* 🆕 悬浮信息卡片 */}
        <HoverInfoCard 
          area={hoverInfo.area}
          position={hoverInfo.position}
          visible={hoverInfo.visible}
          viewLevel={viewLevel}
        />
      </div>
    </div>
  );
};

export default BerlinHeatmapModal;