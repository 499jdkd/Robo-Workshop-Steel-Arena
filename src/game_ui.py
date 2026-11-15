"""Reusable game panels, raised controls, rarity frames and compact resources."""
import flet as ft
from gameplay import compact
from ui_shared import INK,MUTED,GOLD,badge,card,tint

PAINTS={'gold':('#FFE879','#EEA41B'),'green':('#72F3A6','#209B69'),'blue':('#55D7FF','#2264AD'),'purple':('#B29AFF','#7040B4')}

def game_button(label,on_click,*,kind='gold',key=None,disabled=False,icon=None,expand=None):
    top,bottom=PAINTS[kind]
    button=ft.Button(label,on_click=on_click,key=key,icon=icon,disabled=disabled,width=float('inf'),
      style=ft.ButtonStyle(bgcolor='#00000000',color='#102443' if kind in {'gold','green'} else INK,
       elevation=0,padding=ft.Padding.symmetric(horizontal=9,vertical=10),shape=ft.RoundedRectangleBorder(radius=10),
       text_style=ft.TextStyle(size=12,weight=ft.FontWeight.BOLD,font_family='Roboto')))
    return ft.Container(button,expand=expand,border_radius=11,border=ft.Border.all(1,top),
      gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER,end=ft.Alignment.BOTTOM_CENTER,colors=[top,bottom]),
      shadow=ft.BoxShadow(color='#AA020A19',offset=ft.Offset(0,4),blur_radius=2),opacity=.45 if disabled else 1)

def resource_hud(state):
    from collection_progress import ensure
    data=ensure(state)
    values=(('credits',compact(state.coin),GOLD),('food',compact(state.food),'#69E0AF'),('crystal',compact(data['crystals']),'#CC98FF'))
    return ft.Row([ft.Container(ft.Row([badge(icon,23),ft.Text(value,color=INK,size=12,weight=ft.FontWeight.BOLD,expand=True,max_lines=1)],spacing=4),
        expand=True,padding=ft.Padding.symmetric(horizontal=6,vertical=6),border_radius=9,border=ft.Border.all(1,tint(color,.4)),bgcolor='#122A49') for icon,value,color in values],spacing=6)

def section_title(title,subtitle='',trailing=None):
    return ft.Row([ft.Column([ft.Text(title,color=INK,size=19,weight=ft.FontWeight.BOLD),*([ft.Text(subtitle,color=MUTED,size=10)] if subtitle else [])],spacing=3,expand=True),*([trailing] if trailing else [])],spacing=8)

def tabs(labels,selected,select):
    return ft.Row([ft.Button(label,on_click=lambda _,i=i:select(i),style=ft.ButtonStyle(
       bgcolor='#F8BC32' if i==selected else '#203C65',color='#132544' if i==selected else INK,
       elevation=2,side=ft.BorderSide(1,'#FFE47B' if i==selected else '#5774A1'),
       padding=ft.Padding.symmetric(horizontal=10,vertical=10),shape=ft.RoundedRectangleBorder(radius=9),
       text_style=ft.TextStyle(size=11,weight=ft.FontWeight.BOLD,font_family='Roboto'))) for i,label in enumerate(labels)],spacing=6,scroll=ft.ScrollMode.AUTO)

def stat_chip(title,value,color='#77D8FF'):
    return ft.Container(ft.Column([ft.Text(title,color=MUTED,size=10),ft.Text(str(value),color=color,size=16,weight=ft.FontWeight.BOLD)],spacing=3),
       col=6,padding=10,bgcolor='#0E2543',border=ft.Border.all(1,'#35577F'),border_radius=9)
