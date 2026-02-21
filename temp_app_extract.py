            import plotly.graph_objects as go
            plot_df = hist_df.copy()
            # Clip PE for better visualization
            plot_df['raw_pe'] = plot_df['pe']
            plot_df['pe'] = plot_df['pe'].clip(lower=-50, upper=200)
            
            # Pre-calculate medians
            pe_median = float(plot_df['pe'].median())
            price_median = float(plot_df['price'].median())
            plot_df['pe_median'] = pe_median
            plot_df['price_median'] = price_median

            # Phase Translation
            # Check if columns exist
            if 'driver_phase' in plot_df.columns:
                phase_map = {
                    "Healthy": "业绩驱动 (Healthy)", 
                    "Overheated": "估值驱动 (Overheated)", 
                    "Neutral": "其他 (Neutral)"
                }
                plot_df['driver_phase_cn'] = plot_df['driver_phase'].map(phase_map)
                
            base = alt.Chart(plot_df).encode(x=alt.X('trade_date:T', axis=alt.Axis(title='日期', format='%Y-%m')))
            hover = alt.selection_point(fields=['trade_date'], nearest=True, on='mouseover', empty=False, clear='mouseout')
            
            # 1. PE Layer (Left Axis)
            pe_line = base.mark_line(color='#E67E22', strokeDash=[5, 5], opacity=0.5).encode(
                y=alt.Y('pe:Q', axis=alt.Axis(title='PE', titleColor='#E67E22', grid=False))
            )
            pe_median_rule = alt.Chart(plot_df.head(1)).mark_rule(color='#E67E22', strokeDash=[2, 2], opacity=0.8).encode(
                y=alt.Y('pe_median:Q')
            )
            pe_layer = alt.layer(pe_line, pe_median_rule)

            # 2. Price Layer (Right Axis)
            price_line = base.mark_line(color='#BDC3C7', size=1.5).encode(
                y=alt.Y('price:Q', axis=alt.Axis(title='股价 (Price)', titleColor='#2E86C1'))
            )
            price_median_rule = alt.Chart(plot_df.head(1)).mark_rule(color='#2E86C1', strokeDash=[2, 2], opacity=0.6).encode(
                y=alt.Y('price_median:Q')
            )
            
            layers = [pe_line, pe_median_rule, price_line, price_median_rule]
            
            if 'driver_phase_cn' in plot_df.columns:
                domain = ["业绩驱动 (Healthy)", "估值驱动 (Overheated)", "其他 (Neutral)"]
                range_ = ['#2ECC71', '#E74C3C', '#BDC3C7']
                price_dots = base.mark_circle(size=30, opacity=0.8).encode(
                    y='price:Q', 
                    color=alt.Color('driver_phase_cn:N', 
                                  scale=alt.Scale(domain=domain, range=range_),
                                  legend=alt.Legend(orient='bottom', title='行情驱动分类'))
                ).transform_filter(alt.datum.driver_phase_cn != '其他 (Neutral)')
                layers.append(price_dots)
            
            # Selectors
            selectors = base.mark_point().encode(
                x='trade_date:T', 
                opacity=alt.value(0), 
                tooltip=['trade_date:T', 'price:Q', 'raw_pe:Q']
            ).add_params(hover)
            layers.append(selectors)
            
            chart = alt.layer(*layers).resolve_scale(y='independent').properties(height=280)
            
            st.altair_chart(chart, use_container_width=True)
        else:
             st.caption("暂无足够数据生成走势图")
