from rest_framework import serializers
from .models import RestaurantWebsiteSettings, Testimonial


class RestaurantWebsiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantWebsiteSettings
        fields = [
            "id",
            "theme_id",
            "color_palette",
            "custom_primary_hex",
            "tagline",
            "hero_title",
            "hero_subtitle",
            "hero_badge_text",
            "hero_cta_text",
            "hero_image_url",
            "about_title",
            "about_story",
            "chef_name",
            "chef_title",
            "chef_quote",
            "chef_image_url",
            "opening_hours_text",
            "address",
            "phone",
            "email",
            "instagram_url",
            "facebook_url",
            "tiktok_url",
            "delivery_fee",
            "min_delivery_order",
            "estimated_delivery_mins",
            "accepting_online_orders",
            "accepting_reservations",
            "qr_ordering_enabled",
            "gallery_json",
            "highlights_json",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class TestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = [
            "id",
            "guest_name",
            "guest_role",
            "rating",
            "comment",
            "dish_ordered",
            "visit_date",
            "avatar_url",
            "is_featured",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
