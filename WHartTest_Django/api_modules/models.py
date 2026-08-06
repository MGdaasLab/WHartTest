from django.db import models
from django.contrib.auth.models import User


class ApiModule(models.Model):
    name = models.CharField(max_length=100, verbose_name='Module Name')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='api_modules',
        verbose_name='Project',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Parent Module',
    )
    description = models.TextField(null=True, blank=True, verbose_name='Description')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_modules_created',
        verbose_name='Created By',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    level = models.PositiveSmallIntegerField(default=1, verbose_name='Module Level')
    order = models.IntegerField(default=0, verbose_name='Order')

    class Meta:
        verbose_name = 'API Module'
        verbose_name_plural = 'API Modules'
        ordering = ['project', 'level', 'order', 'id']

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.level > 5:
            raise ValidationError('Module level cannot exceed 5.')
        if self.parent and self.parent.project_id != self.project_id:
            raise ValidationError('Parent module must belong to the same project.')
        self.level = (self.parent.level + 1) if self.parent else 1

    def save(self, *args, **kwargs):
        old_level = None
        if self.pk:
            try:
                old_level = ApiModule.objects.get(pk=self.pk).level
            except ApiModule.DoesNotExist:
                pass
        self.clean()
        super().save(*args, **kwargs)
        if old_level is not None and old_level != self.level:
            self.update_descendants_level()

    def get_all_descendant_ids(self):
        """Get all descendant IDs recursively (including self)."""
        ids = [self.id]
        for child in self.children.all():
            ids.extend(child.get_all_descendant_ids())
        return ids

    def get_max_depth(self):
        """Get the maximum depth of this module subtree (minimum depth is 1)."""
        children = self.children.all()
        if not children:
            return 1
        return 1 + max(child.get_max_depth() for child in children)

    def update_descendants_level(self):
        """Recursively update levels of all descendants."""
        for child in self.children.all():
            child.save()

    def get_ancestors(self):
        """Get all ancestor modules."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def get_descendants(self):
        """Get all descendant modules."""
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants
