# -*- coding: utf-8 -*-
from gradio_client import Client, handle_file
import config
def get_tags(file_path):
	client = Client(config.GD_client)
	result = client.predict(
			image=handle_file(file_path),
			model_repo=config.GD_model,
			general_thresh=config.GD_general_thresh,
			general_mcut_enabled=False,
			character_thresh=config.GD_character_thresh,
			character_mcut_enabled=False,
			api_name="/predict"
	)
	tags_string = result[0]
	return tags_string
