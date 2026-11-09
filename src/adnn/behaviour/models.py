"""Local open-weight model adapter. No external action tools or paid APIs."""


class TransformersModel:
    def __init__(self, model_id, revision, seed=42, max_new_tokens=256):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

        if not revision or revision == "main":
            raise ValueError("Supply the immutable revision selected for this experiment, not main")
        set_seed(seed)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, revision=revision, torch_dtype=torch.float16, device_map="auto",
        ).eval()
        self.max_new_tokens = max_new_tokens

    def __call__(self, messages):
        import torch

        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
        inputs = self.tokenizer(text, return_tensors="pt", add_special_tokens=False)
        inputs = inputs.to(self.model.device)
        with torch.inference_mode():
            output = self.model.generate(
                **inputs, do_sample=False, max_new_tokens=self.max_new_tokens,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        return self.tokenizer.decode(
            output[0, inputs.input_ids.shape[1]:], skip_special_tokens=True,
        )
