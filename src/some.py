import flet as ft


@ft.component
def make_card(
    image_src, title_widget, price_widget, on_click, ref, bars, progress_text
):
    return ft.Container(
        width=160,
        padding=15,
        bgcolor="#f0f0f0",
        border_radius=15,
        content=ft.Column(
            [
                ft.Image(image_src, width=50),
                title_widget,
                progress_text,
                ft.Container(
                    content=price_widget, padding=ft.Padding.symmetric(vertical=5)
                ),
                ft.ElevatedButton("Buy", on_click=on_click, ref=ref),
                ft.Container(height=5),
                bars,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    double_click_card = make_card(
        "image5.png",
        text_double_click_label,
        text_double_click_price,
        buy_double_click,
        ref_double_click,
        double_click_bars,
        text_dc_progress,
    )
    auto_click_card = make_card(
        "robot2.png",
        text_auto_click_label,
        text_auto_click_price,
        buy_auto_click,
        ref_auto_click,
        auto_click_bars,
        text_ac_progress,
    )
    offline_card = make_card(
        "image4.png",
        text_offline_label,
        text_offline_price,
        buy_offline_income,
        ref_offline,
        offline_bars,
        text_off_progress,
    )
    boost_card = make_card(
        "boost.png",
        text_boost_label,
        text_boost_price,
        buy_boost,
        ref_boost,
        boost_bars,
        text_boost_progress,
    )


def main(page: ft.Page):

    def add_text_field(e):
        page.add(ft.TextField(label="Name"))

    page.add(
        ft.ElevatedButton("AddTextField", on_click=add_text_field),
    )


ft.app(main)
